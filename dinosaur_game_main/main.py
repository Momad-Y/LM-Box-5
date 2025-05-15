import pygame
import sys
import random
import threading
import cv2
import mediapipe as mp

class JumpDetector:
    def __init__(self, camera_index=0, ankle_ground_threshold=0.15):
        self.camera_index = camera_index
        self.ankle_ground_threshold = ankle_ground_threshold
        self.cap = cv2.VideoCapture(camera_index)
        self.mp_pose = mp.solutions.pose
        self.pose = self.mp_pose.Pose()
        self.mp_draw = mp.solutions.drawing_utils

    def detect_jump(self):
        while self.cap.isOpened():
            ret, frame = self.cap.read()
            if not ret:
                break

            frame_height, frame_width, _ = frame.shape
            rgb_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            result = self.pose.process(rgb_frame)

            jump_detected = False
            if result.pose_landmarks:
                self.mp_draw.draw_landmarks(frame, result.pose_landmarks, self.mp_pose.POSE_CONNECTIONS)
                landmarks = result.pose_landmarks.landmark

                left_ankle_y = int(landmarks[self.mp_pose.PoseLandmark.LEFT_ANKLE].y * frame_height)
                right_ankle_y = int(landmarks[self.mp_pose.PoseLandmark.RIGHT_ANKLE].y * frame_height)

                ground_level = frame_height
                left_distance_from_ground = ground_level - left_ankle_y
                right_distance_from_ground = ground_level - right_ankle_y

                if (left_distance_from_ground > ground_level * self.ankle_ground_threshold and
                    right_distance_from_ground > ground_level * self.ankle_ground_threshold):
                    jump_detected = True

            text_color = (0, 255, 0) if jump_detected else (0, 0, 255)
            cv2.putText(frame, f"Jump detected: {jump_detected}", (10, 30), cv2.FONT_HERSHEY_SIMPLEX, 1, text_color, 2)
            cv2.imshow('Jump Detection', frame)

            if cv2.waitKey(1) & 0xFF == ord('q'):
                break

            yield jump_detected

        self.cap.release()
        cv2.destroyAllWindows()

def run_dino_game(screen=None):
    """
    Run the Dino game either as standalone or from the main menu
    
    Args:
        screen: Optional pygame surface to use (for menu integration)
    """
    if not pygame.get_init():
        pygame.init()
    
    # Use provided screen or create a new one
    if screen is None:
        screen = pygame.display.set_mode((800, 720))
        pygame.display.set_caption("Dino Game")
    
    clock = pygame.time.Clock()
    
    # Get full path for assets
    import os
    current_dir = os.path.dirname(os.path.abspath(__file__))
    font_path = os.path.join(current_dir, "assets", "PressStart2P-Regular.ttf")
    game_font = pygame.font.Font(font_path, 24)

det = JumpDetector()

class Cloud(pygame.sprite.Sprite):
    def __init__(self, image, x_pos, y_pos):
        super().__init__()
        self.image = image
        self.x_pos = x_pos
        self.y_pos = y_pos
        self.rect = self.image.get_rect(center=(self.x_pos, self.y_pos))

    def update(self):
        self.rect.x -= 1

class Dino(pygame.sprite.Sprite):
    def __init__(self, x_pos, y_pos):
        super().__init__()
        self.running_sprites = []
        self.ducking_sprites = []

        self.running_sprites.append(pygame.transform.scale(
            pygame.image.load("assets/Dino1.png"), (80, 100)))
        self.running_sprites.append(pygame.transform.scale(
            pygame.image.load("assets/Dino2.png"), (80, 100)))

        self.ducking_sprites.append(pygame.transform.scale(
            pygame.image.load(f"assets/DinoDucking1.png"), (110, 60)))
        self.ducking_sprites.append(pygame.transform.scale(
            pygame.image.load(f"assets/DinoDucking2.png"), (110, 60)))

        self.x_pos = x_pos
        self.y_pos = y_pos
        self.current_image = 0
        self.image = self.running_sprites[self.current_image]
        self.rect = self.image.get_rect(center=(self.x_pos, self.y_pos))
        self.velocity = 50
        self.gravity = 4.5
        self.ducking = False

    def jump(self):
        jump_sfx.play()
        if self.rect.centery >= 360:
            while self.rect.centery - self.velocity > 40:
                self.rect.centery -= 1

    def duck(self):
        self.ducking = True
        self.rect.centery = 380

    def unduck(self):
        self.ducking = False
        self.rect.centery = 360

    def apply_gravity(self):
        if self.rect.centery <= 360:
            self.rect.centery += self.gravity

    def update(self):
        self.animate()
        self.apply_gravity()

    def animate(self):
        self.current_image += 0.05
        if self.current_image >= 2:
            self.current_image = 0

        if self.ducking:
            self.image = self.ducking_sprites[int(self.current_image)]
        else:
            self.image = self.running_sprites[int(self.current_image)]

class Cactus(pygame.sprite.Sprite):
    def __init__(self, x_pos, y_pos):
        super().__init__()
        self.x_pos = x_pos
        self.y_pos = y_pos
        self.sprites = []
        for i in range(1, 7):
            current_sprite = pygame.transform.scale(
                pygame.image.load(f"assets/cacti/cactus{i}.png"), (100, 100))
            self.sprites.append(current_sprite)
        self.image = random.choice(self.sprites)
        self.rect = self.image.get_rect(center=(self.x_pos, self.y_pos))

    def update(self):
        self.x_pos -= game_speed
        self.rect = self.image.get_rect(center=(self.x_pos, self.y_pos))

class Ptero(pygame.sprite.Sprite):
    def __init__(self):
        super().__init__()
        self.x_pos = 820
        self.y_pos = random.choice([280, 295, 350])
        self.sprites = []
        self.sprites.append(
            pygame.transform.scale(
                pygame.image.load("assets/Ptero1.png"), (84, 62)))
        self.sprites.append(
            pygame.transform.scale(
                pygame.image.load("assets/Ptero2.png"), (84, 62)))
        self.current_image = 0
        self.image = self.sprites[self.current_image]
        self.rect = self.image.get_rect(center=(self.x_pos, self.y_pos))

    def update(self):
        self.animate()
        self.x_pos -= game_speed
        self.rect = self.image.get_rect(center=(self.x_pos, self.y_pos))

    def animate(self):
        self.current_image += 0.025
        if self.current_image >= 2:
            self.current_image = 0
        self.image = self.sprites[int(self.current_image)]

# Variables

game_speed = 5
jump_count = 10
player_score = 0
game_over = False
obstacle_timer = 0
obstacle_spawn = False
obstacle_cooldown = 1000

# Surfaces

ground = pygame.image.load("assets/ground.png")
ground = pygame.transform.scale(ground, (800, 20))
ground_x = 0
ground_rect = ground.get_rect(center=(400, 400))
cloud = pygame.image.load("assets/cloud.png")
cloud = pygame.transform.scale(cloud, (200, 80))

# Groups

cloud_group = pygame.sprite.Group()
obstacle_group = pygame.sprite.Group()
dino_group = pygame.sprite.GroupSingle()
ptero_group = pygame.sprite.Group()

# Objects
dinosaur = Dino(50, 360)
dino_group.add(dinosaur)

# Sounds
death_sfx = pygame.mixer.Sound("assets/sfx/lose.mp3")
points_sfx = pygame.mixer.Sound("assets/sfx/100points.mp3")
jump_sfx = pygame.mixer.Sound("assets/sfx/jump.mp3")

# Events
CLOUD_EVENT = pygame.USEREVENT
pygame.time.set_timer(CLOUD_EVENT, 3000)

# Functions

def end_game():
    global player_score, game_speed
    game_over_text = game_font.render("Game Over!", True, "black")
    game_over_rect = game_over_text.get_rect(center=(400, 300))
    score_text = game_font.render(f"Score: {int(player_score)}", True, "black")
    score_rect = score_text.get_rect(center=(400, 340))
    screen.blit(game_over_text, game_over_rect)
    screen.blit(score_text, score_rect)
    game_speed = 5
    cloud_group.empty()
    obstacle_group.empty()

# Start jump detection in a separate thread
jump_detected = False

def jump_detection_thread():
    global jump_detected
    for detected in det.detect_jump():
        jump_detected = detected

jump_thread = threading.Thread(target=jump_detection_thread)
jump_thread.start()

while True:
    
    keys = pygame.key.get_pressed()
    if keys[pygame.K_DOWN]:
        dinosaur.duck()
    else:
        if dinosaur.ducking:
            dinosaur.unduck()
    for event in pygame.event.get():
        if event.type == pygame.QUIT:
            det.cap.release()
            pygame.quit()
            sys.exit()
        if event.type == CLOUD_EVENT:
            current_cloud_y = random.randint(50, 300)
            current_cloud = Cloud(cloud, 900, current_cloud_y)
            cloud_group.add(current_cloud)

    if jump_detected:
        dinosaur.jump()
        jump_detected = False
        if game_over:
            game_over = False
            game_speed = 5
            player_score = 0

    screen.fill("white")

    # Collisions
    if pygame.sprite.spritecollide(dino_group.sprite, obstacle_group, False):
        game_over = True
        death_sfx.play()
    if game_over:
        end_game()
    # End of game_over block
    
    if not game_over:
        game_speed += 0.0025
        if round(player_score, 1) % 100 == 0 and int(player_score) > 0:
            points_sfx.play()

        if pygame.time.get_ticks() - obstacle_timer >= obstacle_cooldown:
            obstacle_spawn = True

        if obstacle_spawn:
            obstacle_random = random.randint(1, 50)
            if obstacle_random in range(1, 7):
                new_obstacle = Cactus(800, 340)
                obstacle_group.add(new_obstacle)
                obstacle_timer = pygame.time.get_ticks()
                obstacle_spawn = False
            elif obstacle_random in range(7, 10):
                new_obstacle = Ptero()
                obstacle_group.add(new_obstacle)
                obstacle_timer = pygame.time.get_ticks()
                obstacle_spawn = False
                
        player_score += 0.1
        player_score_surface = game_font.render(
            str(int(player_score)), True, ("black"))
        screen.blit(player_score_surface, (670, 10))
        
        cloud_group.update()
        cloud_group.draw(screen)
        
        ptero_group.update()
        ptero_group.draw(screen)
        
        dino_group.update()
        dino_group.draw(screen)
        
        obstacle_group.update()
        obstacle_group.draw(screen)
        
        ground_x -= game_speed

        screen.blit(ground, (ground_x, 360))
        screen.blit(ground, (ground_x + 800, 360))

        if ground_x <= -800:
            ground_x = 0

    clock.tick(120)
    pygame.display.update()