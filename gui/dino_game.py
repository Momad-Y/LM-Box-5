import pygame
import sys
import random
import threading
import cv2
import mediapipe as mp
import os

# Get the absolute path to the dino assets directory
CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
ASSETS_DIR = os.path.join(CURRENT_DIR, "..", "dinosaur_game_main", "assets")

# Replace race.py's DuckDetector with our PoseDetector that can detect both jump and duck
class PoseDetector:
    def __init__(self, camera_index=0, existing_cap=None):
        # Use existing camera if provided (from GUI class), otherwise try to initialize a new one
        if existing_cap is not None:
            self.cap = existing_cap
            # Explicitly check if the camera is actually opened
            try:
                is_opened = self.cap.isOpened()
                print(f"Camera from GUI is opened: {is_opened}")
                self.camera_working = is_opened
                
                # Add a test read to verify the camera is truly working
                if is_opened:
                    test_ret, test_frame = self.cap.read()
                    if test_ret and test_frame is not None:
                        print("Successfully read a test frame from GUI camera")
                        self.camera_working = True
                    else:
                        print("Failed to read test frame from GUI camera")
                        self.camera_working = False
                        
                if self.camera_working:
                    print("Successfully using existing camera from GUI class")
            except Exception as e:
                print(f"Error checking existing camera: {e}")
                self.camera_working = False
        
        # If existing camera failed or wasn't provided, try to initialize a new one
        if not hasattr(self, 'cap') or not self.camera_working:
            print("Existing camera not working, trying new camera")
            # Try different camera indices
            self.cap = cv2.VideoCapture(camera_index)
            self.camera_working = self.cap.isOpened()
            
            if not self.camera_working:
                print("Trying alternate camera index 1")
                self.cap = cv2.VideoCapture(1)
                self.camera_working = self.cap.isOpened()
                
            if not self.camera_working:
                print("Trying alternate camera index 2")
                self.cap = cv2.VideoCapture(2)
                self.camera_working = self.cap.isOpened()
                
            if not self.camera_working:
                print("WARNING: Could not open any camera. Using keyboard controls instead.")
                self.camera_working = False
        self.mp_pose = mp.solutions.pose
        self.pose = self.mp_pose.Pose(min_detection_confidence=0.5, min_tracking_confidence=0.5)
        self.mp_draw = mp.solutions.drawing_utils
        
        # Initialize lines positions (will be set during runtime)
        self.jump_line_y = 0
        self.duck_line_y = 0
        self.lines_initialized = False
        
        # For continuous detection in a thread
        self.running = True
        self.jump_detected = False
        self.duck_detected = False

    def detect_pose_continuous(self):
        """Run in a separate thread to continuously detect pose"""
        if not self.camera_working:
            print("Camera not available. Using keyboard controls instead.")
            print("Press UP arrow to jump, DOWN arrow to duck")
            return
        
        self.current_frame = None  # Store the latest frame
        start_time = pygame.time.get_ticks()
        consecutive_failures = 0
        frame_count = 0
        
        # Diagnostic info
        try:
            print(f"Camera is open: {self.cap.isOpened()}")
            print(f"Camera width: {self.cap.get(cv2.CAP_PROP_FRAME_WIDTH)}")
            print(f"Camera height: {self.cap.get(cv2.CAP_PROP_FRAME_HEIGHT)}")
        except Exception as e:
            print(f"Error getting camera properties: {e}")
        
        # Main detection loop
        while self.running:
            # First check if camera is still open
            try:
                if not self.cap.isOpened():
                    consecutive_failures += 1
                    print(f"Camera appears closed, consecutive failures: {consecutive_failures}")
                    pygame.time.wait(100)
                    
                    # After 10 failures, try to reopen if using our own camera (not from GUI)
                    if consecutive_failures >= 10:
                        try:
                            print("Attempting to recover camera connection...")
                            self.cap.release()  # Make sure to release the old one
                            self.cap = cv2.VideoCapture(0)  # Try to reopen
                            if not self.cap.isOpened():
                                print("Still can't open camera.")
                            else:
                                print("Camera recovered!")
                                consecutive_failures = 0
                        except Exception as e:
                            print(f"Error trying to recover camera: {e}")
                        
                    if consecutive_failures >= 20:
                        print("Too many failures, giving up on camera")
                        self.camera_working = False
                        break
                        
                    continue
                    
                # If we get here, the camera is open
                ret, frame = self.cap.read()
                if not ret or frame is None or frame.size == 0:
                    print("Failed to read valid frame from camera")
                    consecutive_failures += 1
                    pygame.time.wait(100)
                    continue
                    
                # We got a valid frame, reset failure counter
                consecutive_failures = 0
                frame_count += 1
                
                # Debug info every 100 frames
                if frame_count % 100 == 0:
                    elapsed_time = pygame.time.get_ticks() - start_time
                    fps = frame_count / (elapsed_time / 1000)
                    print(f"Frame rate: {fps:.2f} FPS")
                    
                frame = cv2.flip(frame, 1)  # Flip for mirror effect
                frame_height, frame_width, _ = frame.shape
                
                # Set lines positions if not initialized
                if not self.lines_initialized:
                    self.jump_line_y = int(frame_height * 0.4)  # Upper 40% of the frame
                    self.duck_line_y = int(frame_height * 0.6)  # Lower 60% of the frame
                    self.lines_initialized = True
                
                # Draw the lines
                cv2.line(frame, (0, self.jump_line_y), (frame_width, self.jump_line_y), (0, 255, 0), 2)
                cv2.line(frame, (0, self.duck_line_y), (frame_width, self.duck_line_y), (0, 0, 255), 2)
                
                # Process pose detection
                rgb_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
                result = self.pose.process(rgb_frame)
                
                self.jump_detected = False
                self.duck_detected = False
                
                if result.pose_landmarks:
                    # Don't draw all landmarks, only get the data we need
                    landmarks = result.pose_landmarks.landmark
                    
                    # Get nose landmark
                    if self.mp_pose.PoseLandmark.NOSE.value < len(landmarks):
                        nose = landmarks[self.mp_pose.PoseLandmark.NOSE.value]
                        nose_x = int(nose.x * frame_width)
                        nose_y = int(nose.y * frame_height)
                        
                        # Draw only a point on the nose with a nice marker
                        cv2.circle(frame, (nose_x, nose_y), 10, (0, 0, 255), -1)  # Red filled circle
                        cv2.circle(frame, (nose_x, nose_y), 12, (0, 0, 0), 2)  # Black outline
                        
                        # Check if nose crosses the lines
                        if nose_y < self.jump_line_y:
                            self.jump_detected = True
                            cv2.putText(frame, "JUMP!", (10, 30), cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 255, 0), 2)
                        elif nose_y > self.duck_line_y:
                            self.duck_detected = True
                            cv2.putText(frame, "DUCK!", (10, 30), cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 0, 255), 2)
                
                # Save the latest frame for rendering in pygame
                self.current_frame = frame.copy()
                
                # No need to show in separate window anymore
                if cv2.waitKey(1) & 0xFF == ord('q'):
                    self.running = False
                    break
            except Exception as e:
                print(f"Error in pose detection thread: {e}")
                consecutive_failures += 1
                pygame.time.wait(100)
                
    def stop(self):
        """Stop the detection thread and release resources"""
        self.running = False
        print("Stopping pose detector thread")
        
        # Don't release the camera if it's from the GUI class (external cap)
        # We only want to destroy windows
        try:
            cv2.destroyAllWindows()
            print("OpenCV windows destroyed")
        except Exception as e:
            print(f"Error destroying windows: {e}")
            
        # Mark camera as no longer working to prevent any further usage attempts
        # This doesn't release the camera, just marks it as unavailable for this detector
        self.camera_working = False

    def get_state(self):
        """Return the current jump/duck state"""
        if not self.camera_working:
            # If no camera, return no input from camera
            return False, False
        return self.jump_detected, self.duck_detected
        
    def get_camera_frame(self):
        """Return the current camera frame"""
        # If camera is reported as not working, return None
        if not self.camera_working:
            return None
            
        # If we don't have a current frame but the camera is supposedly working,
        # try to read one directly to recover
        if not hasattr(self, 'current_frame') or self.current_frame is None:
            if hasattr(self, 'cap') and self.cap.isOpened():
                try:
                    ret, frame = self.cap.read()
                    if ret and frame is not None:
                        print("Retrieved camera frame directly in get_camera_frame")
                        self.current_frame = frame
                        return frame
                except Exception as e:
                    print(f"Error reading frame directly: {e}")
            return None
            
        return self.current_frame

class Dino(pygame.sprite.Sprite):
    def __init__(self, pos_x, pos_y):
        super().__init__()
        
        # Load images for different states and scale them up (1.5x larger)
        dino_scale_factor = 1.5  # Increase size by 50%
        
        # Load and scale running images
        dino1 = pygame.image.load(os.path.join(ASSETS_DIR, "Dino1.png"))
        dino2 = pygame.image.load(os.path.join(ASSETS_DIR, "Dino2.png"))
        dino1_size = dino1.get_rect().size
        dino2_size = dino2.get_rect().size
        self.run_imgs = [
            pygame.transform.scale(dino1, (int(dino1_size[0] * dino_scale_factor), int(dino1_size[1] * dino_scale_factor))),
            pygame.transform.scale(dino2, (int(dino2_size[0] * dino_scale_factor), int(dino2_size[1] * dino_scale_factor))),
        ]
        
        # Load and scale jumping image
        jump_img = pygame.image.load(os.path.join(ASSETS_DIR, "DinoJumping.png"))
        jump_size = jump_img.get_rect().size
        self.jump_img = pygame.transform.scale(jump_img, (int(jump_size[0] * dino_scale_factor), int(jump_size[1] * dino_scale_factor)))
        
        # Load and scale ducking images
        duck1 = pygame.image.load(os.path.join(ASSETS_DIR, "DinoDucking1.png"))
        duck2 = pygame.image.load(os.path.join(ASSETS_DIR, "DinoDucking2.png"))
        duck1_size = duck1.get_rect().size
        duck2_size = duck2.get_rect().size
        self.duck_imgs = [
            pygame.transform.scale(duck1, (int(duck1_size[0] * dino_scale_factor), int(duck1_size[1] * dino_scale_factor))),
            pygame.transform.scale(duck2, (int(duck2_size[0] * dino_scale_factor), int(duck2_size[1] * dino_scale_factor))),
        ]
        
        self.run_index = 0
        self.duck_index = 0
        self.image = self.run_imgs[0]  # Initial image
        
        # Set hitbox and position
        self.rect = self.image.get_rect()
        self.rect.x = pos_x
        self.rect.y = pos_y
        self.pos_y_initial = pos_y
        
        # Jump physics
        self.gravity = 0.6
        self.velocity_y = 0
        self.jumping = False
        self.ducking = False
        
        # Animation timer
        self.animation_timer = 0
        
    def update(self, jump_input=False, duck_input=False):
        # Handle jumping
        if jump_input and not self.jumping:
            self.jumping = True
            self.velocity_y = -15
            # Add jump sound
            jump_sound = pygame.mixer.Sound(os.path.join(ASSETS_DIR, "sfx", "jump.mp3"))
            jump_sound.play()
        
        if self.jumping:
            self.velocity_y += self.gravity
            self.rect.y += self.velocity_y
            self.image = self.jump_img
            
            # Check if dino has landed
            if self.rect.y >= self.pos_y_initial:
                self.rect.y = self.pos_y_initial
                self.jumping = False
                self.velocity_y = 0
        
        # Handle ducking
        elif duck_input:
            self.ducking = True
            self.animation_timer += 1
            if self.animation_timer >= 10:
                self.duck_index = (self.duck_index + 1) % 2
                self.image = self.duck_imgs[self.duck_index]
                self.animation_timer = 0
            # Adjust hitbox for ducking
            old_rect = self.rect
            self.rect = self.image.get_rect()
            self.rect.x = old_rect.x
            self.rect.y = self.pos_y_initial + 30  # Adjust y for ducking height
        
        # Running animation
        else:
            self.ducking = False
            self.animation_timer += 1
            if self.animation_timer >= 10:
                self.run_index = (self.run_index + 1) % 2
                self.image = self.run_imgs[self.run_index]
                self.animation_timer = 0
                
            # Reset hitbox for running
            old_rect = self.rect
            self.rect = self.image.get_rect()
            self.rect.x = old_rect.x
            self.rect.y = self.pos_y_initial

class Obstacle(pygame.sprite.Sprite):
    def __init__(self, image, pos_x, pos_y):
        super().__init__()
        self.image = image
        self.rect = self.image.get_rect()
        self.rect.x = pos_x
        self.rect.y = pos_y
        self.speed = 0  # Will be set by update method
        
    def update(self, game_speed):
        self.speed = game_speed
        self.rect.x -= game_speed
        if self.rect.x < -100:  # Remove when off screen
            self.kill()

class Cactus(Obstacle):
    def __init__(self, pos_x, pos_y):
        # Random cactus image
        cactus_num = random.randint(1, 6)
        # Load the cactus image
        cactus_img = pygame.image.load(os.path.join(ASSETS_DIR, "cacti", f"cactus{cactus_num}.png"))
        # Scale up the cactus image by 50%
        obstacle_scale_factor = 1.5
        cactus_size = cactus_img.get_rect().size
        scaled_image = pygame.transform.scale(cactus_img, 
            (int(cactus_size[0] * obstacle_scale_factor), 
             int(cactus_size[1] * obstacle_scale_factor)))
        # Pass the scaled image to the parent class
        super().__init__(scaled_image, pos_x, pos_y)

class Ptero(Obstacle):
    def __init__(self, screen_width=800):
        # Flying pterodactyl - scaled up by 50%
        obstacle_scale_factor = 1.5
        
        # Load pterodactyl images and scale them up
        ptero1 = pygame.image.load(os.path.join(ASSETS_DIR, "Ptero1.png"))
        ptero2 = pygame.image.load(os.path.join(ASSETS_DIR, "Ptero2.png"))
        
        # Get original sizes
        ptero1_size = ptero1.get_rect().size
        ptero2_size = ptero2.get_rect().size
        
        # Scale the images
        self.images = [
            pygame.transform.scale(ptero1, 
                (int(ptero1_size[0] * obstacle_scale_factor), 
                 int(ptero1_size[1] * obstacle_scale_factor))),
            pygame.transform.scale(ptero2, 
                (int(ptero2_size[0] * obstacle_scale_factor), 
                 int(ptero2_size[1] * obstacle_scale_factor)))
        ]
        
        self.index = 0
        self.animation_timer = 0
        # Use more dynamic height based on screen_width for better fullscreen adaptation
        height = random.choice([200, 250, 300])
        # Use screen_width to position off-screen to the right
        super().__init__(self.images[0], screen_width, height)
        
    def update(self, game_speed):
        # Animate wing flapping
        self.animation_timer += 1
        if self.animation_timer >= 15:
            self.index = (self.index + 1) % 2
            self.image = self.images[self.index]
            self.animation_timer = 0
            
        # Move left
        self.rect.x -= game_speed
        if self.rect.x < -100:
            self.kill()

class Cloud(pygame.sprite.Sprite):
    def __init__(self, screen_width=800):
        super().__init__()
        self.image = pygame.image.load(os.path.join(ASSETS_DIR, "cloud.png"))
        self.rect = self.image.get_rect()
        # Position clouds at the right edge of the game area, with screen_width parameter
        self.rect.x = screen_width + random.randint(0, 100)  # Start just off-screen to the right
        self.rect.y = random.randint(50, 200)  # Random height in the sky
        self.speed = random.randint(2, 5)  # Random cloud speed
        
    def update(self):
        self.rect.x -= self.speed
        if self.rect.x < -100:
            self.kill()

# Draw the camera overlay in the corner
def draw_camera_overlay(screen, camera_frame, camera_area):
    if camera_frame is not None:
        # Convert OpenCV BGR to RGB format
        camera_frame = cv2.cvtColor(camera_frame, cv2.COLOR_BGR2RGB)
        # Resize to fit the camera area
        camera_frame = cv2.resize(camera_frame, (camera_area.width, camera_area.height))
        # Convert to pygame surface
        camera_surface = pygame.surfarray.make_surface(camera_frame.swapaxes(0, 1))
        # Draw to screen with proper positioning
        screen.blit(camera_surface, (camera_area.x, camera_area.y))
        
        # Draw a border around the camera
        pygame.draw.rect(screen, (255, 255, 255), camera_area, width=2)

def run_dino_game(screen=None, existing_cap=None, bg_image=None):
    """
    Run the Dino game either as standalone or from the main menu
    
    Args:
        screen: Optional pygame surface to use (for menu integration)
        existing_cap: Optional existing camera capture object from the GUI class
        bg_image: Optional background image from the GUI class (Pong style)
    """
    # Import os here to avoid UnboundLocalError
    import os
    
    # Initialize pygame
    if not pygame.get_init():
        pygame.init()
    
    # Use provided screen or create a new one
    standalone_mode = False
    
    # Get screen dimensions
    if screen is None:
        # Standalone mode - create our own screen
        standalone_mode = True
        try:
            # Make sure os is imported at the beginning of this function
            import os
            
            # Set the window to be centered on the screen
            os.environ['SDL_VIDEO_CENTERED'] = '1'
            
            # Get the current screen resolution for fullscreen
            from screeninfo import get_monitors
            try:
                monitors = get_monitors()
                if monitors:
                    SCREEN_WIDTH = monitors[0].width
                    SCREEN_HEIGHT = monitors[0].height
                else:
                    # Default if monitor detection fails
                    SCREEN_WIDTH = 1920
                    SCREEN_HEIGHT = 1080
            except Exception:
                # Fallback to standard resolution
                SCREEN_WIDTH = 1920
                SCREEN_HEIGHT = 1080
                
            # Create a borderless fullscreen window
            screen = pygame.display.set_mode((SCREEN_WIDTH, SCREEN_HEIGHT), pygame.NOFRAME)
            pygame.display.set_caption("Dino Game with Camera")
        except Exception as e:
            print(f"Error setting up fullscreen: {e}, using default size")
            SCREEN_WIDTH = 1200
            SCREEN_HEIGHT = 600
            screen = pygame.display.set_mode((SCREEN_WIDTH, SCREEN_HEIGHT))
    else:
        # Using provided screen - get its dimensions
        SCREEN_WIDTH = screen.get_width()
        SCREEN_HEIGHT = screen.get_height()
        print(f"Using provided screen with dimensions: {SCREEN_WIDTH}x{SCREEN_HEIGHT}")
    
    # Define game and camera areas
    # Center the game area on screen - now covers the entire screen
    game_area = pygame.Rect(0, 0, SCREEN_WIDTH, SCREEN_HEIGHT)
    
    # Create a smaller camera view that will overlay in a corner
    camera_width = min(SCREEN_WIDTH // 4, 320)  # Smaller camera size for fullscreen
    camera_height = min(SCREEN_HEIGHT // 4, 240)
    camera_area = pygame.Rect(
        SCREEN_WIDTH - camera_width - 20,  # Position in top right corner with padding
        20,  # Top padding
        camera_width, 
        camera_height
    )
    
    # Helper function to draw the camera overlay
    def draw_camera_overlay(screen, frame, camera_area):
        """Draw the camera overlay in the designated corner"""
        if frame is None:
            # Draw a placeholder if no camera frame
            pygame.draw.rect(screen, (40, 40, 40), camera_area)
            pygame.draw.rect(screen, (100, 100, 100), camera_area, 2)  # Border
            return
            
        # Resize the frame to fit in the camera area
        frame_rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        frame_resized = cv2.resize(frame_rgb, (camera_area.width, camera_area.height))
        
        # Convert to pygame surface and display
        cam_surface = pygame.surfarray.make_surface(frame_resized.swapaxes(0, 1))
        screen.blit(cam_surface, (camera_area.left, camera_area.top))
        
        # Add a border around the camera view
        pygame.draw.rect(screen, (200, 200, 200), camera_area, 2)
    
    # Basic game setup
    clock = pygame.time.Clock()
    game_font = pygame.font.Font(os.path.join(ASSETS_DIR, "PressStart2P-Regular.ttf"), 24)
    controls_font = pygame.font.Font(os.path.join(ASSETS_DIR, "PressStart2P-Regular.ttf"), 16)            # Set up pose detection with the existing camera if provided
    pose_detector = PoseDetector(camera_index=0, existing_cap=existing_cap)
    
    # Verify camera state and print verbose information
    if pose_detector.camera_working:
        print("\n=== Camera Information ===")
        print(f"Camera is open: {pose_detector.cap.isOpened()}")
        try:
            print(f"Camera width: {pose_detector.cap.get(cv2.CAP_PROP_FRAME_WIDTH)}")
            print(f"Camera height: {pose_detector.cap.get(cv2.CAP_PROP_FRAME_HEIGHT)}")
            print(f"Camera FPS: {pose_detector.cap.get(cv2.CAP_PROP_FPS)}")
            # Try a test read
            ret, test_frame = pose_detector.cap.read()
            if ret and test_frame is not None:
                print(f"Test read successful - Frame shape: {test_frame.shape}")
                # Reset the frame to give the thread a head start
                pose_detector.current_frame = test_frame
            else:
                print("Test read failed!")
                pose_detector.camera_working = False
        except Exception as e:
            print(f"Error testing camera: {e}")
            pose_detector.camera_working = False
    
    # Only start the thread if camera is working
    if pose_detector.camera_working:
        print("Starting pose detection thread...")
        detection_thread = threading.Thread(target=pose_detector.detect_pose_continuous)
        detection_thread.daemon = True
        detection_thread.start()
    else:
        print("Camera not available. Using keyboard controls instead.")
        # Create a font and text surface for the controls hint
        try:
            controls_font = pygame.font.Font(os.path.join(ASSETS_DIR, "PressStart2P-Regular.ttf"), 12)
            controls_text = controls_font.render("KEYBOARD CONTROLS: UP=JUMP, DOWN=DUCK", True, (255, 0, 0))
        except Exception as e:
            print(f"Error setting up controls hint: {e}")
    
    # Use a solid pink background color instead of image
    # Create a surface for the background with the screen dimensions
    background = pygame.Surface((SCREEN_WIDTH, SCREEN_HEIGHT))
    # Fill the background with pink color (255, 192, 203) is light pink
    background.fill((255, 182, 193))  # Using a nice pink shade
    
    ground = pygame.image.load(os.path.join(ASSETS_DIR, "ground.png"))
    
    # Create sprite groups
    dino_group = pygame.sprite.GroupSingle()
    obstacle_group = pygame.sprite.Group()
    cloud_group = pygame.sprite.Group()
    
    # Calculate ground position based on screen height (scaled properly)
    ground_y = int(SCREEN_HEIGHT * 0.75)  # Place ground at 75% of screen height
    
    # Position dino properly based on ground position - adjust for fullscreen
    dino_x = int(SCREEN_WIDTH * 0.15)  # Position at 15% of screen width
    dino_y = ground_y - 40  # Position dino just above the ground
    dino = Dino(dino_x, dino_y)
    dino_group.add(dino)
    
    # Game variables
    game_speed = 10
    game_over = False
    score = 0
    ground_x = 0
    obstacle_timer = 0
    obstacle_spawn = True
    
    # Cloud spawning timer
    cloud_timer = pygame.time.get_ticks()
    cloud_spawn_time = 3000  # 3 seconds
    
    # Main game loop
    try:
        while True:
            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    pose_detector.stop()
                    if standalone_mode:
                        pygame.quit()
                        sys.exit()
                    else:
                        return  # Return to calling function (menu)
                    
                # Handle ESC key to return to menu
                if event.type == pygame.KEYDOWN and event.key == pygame.K_ESCAPE:
                    pose_detector.stop()
                    return
                    
            # Handle game over state
            if game_over:
                # Draw a semi-transparent overlay for game over
                overlay = pygame.Surface((SCREEN_WIDTH, SCREEN_HEIGHT), pygame.SRCALPHA)
                overlay.fill((0, 0, 0, 180))  # More opaque black
                screen.blit(overlay, (0, 0))
                
                # Create a game over panel with better styling - scale with screen size
                panel_width = min(500, SCREEN_WIDTH//3)  # Don't let panel get too big or too small
                panel_height = min(300, SCREEN_HEIGHT//3)
                panel_x = SCREEN_WIDTH//2 - panel_width//2
                panel_y = SCREEN_HEIGHT//2 - panel_height//2
                
                # Draw panel background - outer border
                pygame.draw.rect(screen, (255, 255, 255), 
                                (panel_x-3, panel_y-3, panel_width+6, panel_height+6), 
                                border_radius=15)
                # Inner panel
                pygame.draw.rect(screen, (50, 50, 50), 
                                (panel_x, panel_y, panel_width, panel_height), 
                                border_radius=12)
                pygame.draw.rect(screen, (30, 30, 30), 
                                (panel_x + 5, panel_y + 5, panel_width - 10, panel_height - 10), 
                                border_radius=10)
                
                # Game over text - styled with a title bar like Pong
                title_bar = pygame.Rect(panel_x, panel_y + 15, panel_width, 50)
                pygame.draw.rect(screen, (0, 0, 0), title_bar)
                
                game_over_text = game_font.render("GAME OVER", True, (255, 0, 0))
                score_text = game_font.render(f"SCORE: {int(score)}", True, (255, 255, 255))
                restart_text = controls_font.render("Press R to Restart", True, (255, 255, 0))
                menu_text = controls_font.render("Press ESC for Menu", True, (255, 255, 0))
                
                # Position text in panel
                screen.blit(game_over_text, (panel_x + panel_width//2 - game_over_text.get_width()//2, panel_y + 30))
                screen.blit(score_text, (panel_x + panel_width//2 - score_text.get_width()//2, panel_y + 100))
                screen.blit(restart_text, (panel_x + panel_width//2 - restart_text.get_width()//2, panel_y + 160))
                screen.blit(menu_text, (panel_x + panel_width//2 - menu_text.get_width()//2, panel_y + 200))
                
                keys = pygame.key.get_pressed()
                if keys[pygame.K_r]:
                    # Reset game
                    game_over = False
                    score = 0
                    game_speed = 10
                    obstacle_group.empty()
                    
                pygame.display.update()
                clock.tick(60)
                continue
                
            # Get camera input
            jump_detected, duck_detected = pose_detector.get_state()
            
            # Handle keyboard controls too
            keys = pygame.key.get_pressed()
            keyboard_jump = keys[pygame.K_SPACE] or keys[pygame.K_UP]
            keyboard_duck = keys[pygame.K_DOWN]
            
            # Update dino
            dino_group.update(jump_detected or keyboard_jump, duck_detected or keyboard_duck)
            
            # Check collision
            if pygame.sprite.spritecollide(dino, obstacle_group, False):
                game_over = True
                # Play game over sound
                game_over_sound = pygame.mixer.Sound(os.path.join(ASSETS_DIR, "sfx", "lose.mp3"))
                game_over_sound.play()
            
            # Draw background for the entire screen first
            screen.blit(background, (0, 0))
            
            # Draw a border around the game area
            game_border = pygame.Rect(10, 10, SCREEN_WIDTH - 20, SCREEN_HEIGHT - 20)
            pygame.draw.rect(screen, (255, 255, 255), game_border, width=3, border_radius=10)
            
            # Title bar at top center with "DINO GAME"
            title_area = pygame.Rect(SCREEN_WIDTH//2 - 150, 20, 300, 40)
            pygame.draw.rect(screen, (0, 0, 0), title_area)
            title_text = game_font.render("DINO GAME", True, (255, 255, 255))
            screen.blit(title_text, (SCREEN_WIDTH//2 - title_text.get_width()//2, 25))
            
            # Display camera feed in the corner if available
            if pose_detector.camera_working:
                camera_frame = pose_detector.get_camera_frame()
                if camera_frame is not None:
                    draw_camera_overlay(screen, camera_frame, camera_area)
                    
                    # Show visual indicators for jump/duck detection
                    if jump_detected:
                        jump_status = controls_font.render("JUMP", True, (0, 255, 0))
                        screen.blit(jump_status, (camera_area.x, camera_area.y + camera_area.height + 10))
                    
                    if duck_detected:
                        duck_status = controls_font.render("DUCK", True, (0, 255, 0))
                        screen.blit(duck_status, (camera_area.x, camera_area.y + camera_area.height + 40))
            else:
                # Show keyboard controls if camera not available
                controls_text = controls_font.render("KEYBOARD CONTROLS: UP=JUMP, DOWN=DUCK", True, (255, 0, 0))
                screen.blit(controls_text, (SCREEN_WIDTH//2 - controls_text.get_width()//2, SCREEN_HEIGHT - 40))
            
            # Spawn clouds - adjust frequency for fullscreen
            current_time = pygame.time.get_ticks()
            if current_time - cloud_timer > cloud_spawn_time:
                new_cloud = Cloud(screen_width=SCREEN_WIDTH)  # Use full screen width for game area
                cloud_group.add(new_cloud)
                cloud_timer = current_time
                cloud_spawn_time = random.randint(1500, 3000)  # 1.5-3 seconds for more clouds in fullscreen
            
            # Spawn obstacles
            if obstacle_spawn:
                if pygame.time.get_ticks() - obstacle_timer > 1500:  # 1.5 seconds between obstacles
                    obstacle_random = random.randint(1, 10)
                    if obstacle_random <= 7:  # 70% chance for cactus
                        new_obstacle = Cactus(SCREEN_WIDTH - 20, ground_y - 40)  # Position on ground at far right
                        obstacle_group.add(new_obstacle)
                    else:  # 30% chance for pterodactyl
                        # For pterodactyl, use random heights relative to the ground
                        height_options = [
                            ground_y - 120,  # Higher position
                            ground_y - 80,   # Medium position 
                            ground_y - 40    # Lower position
                        ]
                        ptero_y = random.choice(height_options)
                        new_obstacle = Ptero(screen_width=SCREEN_WIDTH)  # Full screen width
                        new_obstacle.rect.y = ptero_y  # Set height manually
                        obstacle_group.add(new_obstacle)
                    
                    obstacle_timer = pygame.time.get_ticks()
                    obstacle_spawn = False
            else:
                if pygame.time.get_ticks() - obstacle_timer > random.randint(1500, 3000):
                    obstacle_spawn = True
                    
            # Update score
            score += 0.1
            # Display score in similar style to Pong
            score_bg = pygame.Rect(20, 20, 200, 40)
            pygame.draw.rect(screen, (0, 0, 0), score_bg)
            score_surface = game_font.render(f"Score: {int(score)}", True, (255, 255, 255))
            screen.blit(score_surface, (30, 25))
            
            # Speed up game as score increases
            if int(score) % 100 == 0 and int(score) > 0:
                milestone_score = int(score)
                if milestone_score % 100 == 0 and game_speed < 20:
                    game_speed += 0.5
                    # Play 100 points sound
                    point_sound = pygame.mixer.Sound(os.path.join(ASSETS_DIR, "sfx", "100points.mp3"))
                    point_sound.play()
            
            # Update and draw sprites
            cloud_group.update()
            cloud_group.draw(screen)
            
            dino_group.draw(screen)
            
            obstacle_group.update(game_speed)
            obstacle_group.draw(screen)
            
            # Move and draw ground - scale with screen size
            ground_x -= game_speed
            ground_width = ground.get_width()
            
            # Draw ground across the full game area width, handling fullscreen better
            for i in range(-ground_width, SCREEN_WIDTH + ground_width * 2, ground_width):
                screen.blit(ground, (ground_x + i, ground_y))
                
            if ground_x <= -ground_width:
                ground_x = 0
            
            # Update display
            pygame.display.update()
            clock.tick(60)
    
    except Exception as e:
        print(f"Error in Dino game: {e}")
    finally:
        # Ensure cleanup happens properly
        pose_detector.stop()
        if standalone_mode:
            pygame.quit()
            
if __name__ == "__main__":
    run_dino_game()
