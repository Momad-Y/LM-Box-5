import cv2
import mediapipe as mp

class PoseDetector:
    def __init__(self, camera_index=0):
        # Try different camera indices
        self.cap = cv2.VideoCapture(camera_index)
        if not self.cap.isOpened():
            print("Trying alternate camera index 1")
            self.cap = cv2.VideoCapture(1)
        if not self.cap.isOpened():
            print("Trying alternate camera index 2")
            self.cap = cv2.VideoCapture(2)
        self.mp_pose = mp.solutions.pose
        self.pose = self.mp_pose.Pose(min_detection_confidence=0.5, min_tracking_confidence=0.5)
        self.mp_draw = mp.solutions.drawing_utils
        
        # Initialize lines positions (will be set during runtime)
        self.jump_line_y = 0
        self.duck_line_y = 0
        self.lines_initialized = False

    def detect_pose(self, frame):
        frame_height, frame_width, _ = frame.shape
        rgb_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        result = self.pose.process(rgb_frame)

        jump_detected = False
        duck_detected = False
        nose_position = None

        # Set lines positions if not initialized
        if not self.lines_initialized:
            self.jump_line_y = int(frame_height * 0.4)  # Upper 40% of the frame
            self.duck_line_y = int(frame_height * 0.7)  # Lower 70% of the frame
            self.lines_initialized = True
        
        # Draw the lines
        cv2.line(frame, (0, self.jump_line_y), (frame_width, self.jump_line_y), (0, 255, 0), 2)
        cv2.line(frame, (0, self.duck_line_y), (frame_width, self.duck_line_y), (0, 0, 255), 2)
        
        if result.pose_landmarks:
            self.mp_draw.draw_landmarks(frame, result.pose_landmarks, self.mp_pose.POSE_CONNECTIONS)
            landmarks = result.pose_landmarks.landmark

            # Get nose landmark
            if self.mp_pose.PoseLandmark.NOSE in range(len(landmarks)):
                nose = landmarks[self.mp_pose.PoseLandmark.NOSE]
                nose_x, nose_y = int(nose.x * frame_width), int(nose.y * frame_height)
                nose_position = (nose_x, nose_y)
                
                # Draw circle on nose
                cv2.circle(frame, nose_position, 10, (255, 0, 0), cv2.FILLED)
                
                # Check if nose crosses the lines
                if nose_y < self.jump_line_y:
                    jump_detected = True
                    cv2.putText(frame, "JUMP!", (10, 30), cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 255, 0), 2)
                elif nose_y > self.duck_line_y:
                    duck_detected = True
                    cv2.putText(frame, "DUCK!", (10, 30), cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 0, 255), 2)

        return jump_detected, duck_detected, nose_position, frame

if __name__ == "__main__":
    detector = PoseDetector(camera_index=0)  # Use default camera
    print("Press 'q' to quit")
    
    while True:
        ret, frame = detector.cap.read()
        if not ret:
            print("Failed to read from camera. Exiting...")
            break

        # Flip frame horizontally for a selfie-view
        frame = cv2.flip(frame, 1)
        
        jump_detected, duck_detected, nose_position, annotated_frame = detector.detect_pose(frame)
        
        # Display status in the frame
        status = "NORMAL"
        if jump_detected:
            status = "JUMP"
        elif duck_detected:
            status = "DUCK"
            
        cv2.putText(annotated_frame, f"Status: {status}", (10, 70), 
                    cv2.FONT_HERSHEY_SIMPLEX, 0.7, (255, 255, 255), 2)
        
        if nose_position:
            cv2.putText(annotated_frame, f"Nose Y: {nose_position[1]}", (10, 100), 
                        cv2.FONT_HERSHEY_SIMPLEX, 0.7, (255, 255, 255), 2)
        
        cv2.imshow('Nose Position Detector', annotated_frame)
        if cv2.waitKey(1) & 0xFF == ord('q'):
            break

    detector.cap.release()
    cv2.destroyAllWindows()
