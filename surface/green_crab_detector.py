#!/usr/bin/env python3
"""Simple scaffold for European green crab image detection.

This is a starting point for auto image recognition. It provides a
placeholder `detect_crab` function and a minimal CLI that reads from a
camera or image file. Install OpenCV (`pip install opencv-python`) to use.
"""
import sys
try:
    import cv2
except Exception:
    cv2 = None


def detect_crab(frame):
    """Placeholder detection function.

    Return a list of bounding boxes [(x,y,w,h), ...] where crabs are detected.
    Implement a trained model or heuristic here.
    """
    # TODO: implement model-based detection (e.g., TensorFlow/PyTorch/ONNX)
    # For now, return empty list so the scaffold runs without a model.
    return []


def main():
    if cv2 is None:
        print("OpenCV not available. Install with: pip install opencv-python")
        sys.exit(1)

    src = 0
    if len(sys.argv) > 1:
        src = sys.argv[1]

    cap = None
    if isinstance(src, str) and (src.endswith('.jpg') or src.endswith('.png')):
        frame = cv2.imread(src)
        boxes = detect_crab(frame)
        print('Detected boxes:', boxes)
        for (x, y, w, h) in boxes:
            cv2.rectangle(frame, (x, y), (x + w, y + h), (0, 255, 0), 2)
        cv2.imshow('detections', frame)
        cv2.waitKey(0)
    else:
        try:
            cap = cv2.VideoCapture(int(src))
        except Exception:
            cap = cv2.VideoCapture(src)

        if not cap.isOpened():
            print('Failed to open video source:', src)
            sys.exit(1)

        while True:
            ret, frame = cap.read()
            if not ret:
                break
            boxes = detect_crab(frame)
            for (x, y, w, h) in boxes:
                cv2.rectangle(frame, (x, y), (x + w, y + h), (0, 255, 0), 2)
            cv2.imshow('green crab detector', frame)
            if cv2.waitKey(1) & 0xFF == ord('q'):
                break

        cap.release()
        cv2.destroyAllWindows()


if __name__ == '__main__':
    main()
