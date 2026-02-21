import tkinter as tk
from tkinter import ttk


def draw_joystick(canvas, x, y, radius, lx, ly, deadzone):
    """Draw a joystick visualization on the canvas.
    
    Args:
        canvas: tkinter Canvas widget
        x, y: center position
        radius: size of the joystick circle
        lx, ly: normalized axis values (-1 to 1)
        deadzone: deadzone threshold (0 to 1)
    """
    # Draw circle background
    canvas.create_oval(x - radius, y - radius, x + radius, y + radius, 
                       fill="lightgray", outline="black", width=2)
    
    # Draw deadzone circle (thin red circle)
    deadzone_radius = (radius - 10) * deadzone
    canvas.create_oval(x - deadzone_radius, y - deadzone_radius, 
                       x + deadzone_radius, y + deadzone_radius,
                       outline="blue", width=1)
    
    # Draw center
    canvas.create_oval(x - 5, y - 5, x + 5, y + 5, fill="black", outline="black")
    
    # Draw stick position
    stick_x = x + lx * (radius - 10)
    stick_y = y - ly * (radius - 10)  # negate ly because canvas y increases downward
    canvas.create_oval(stick_x - 8, stick_y - 8, stick_x + 8, stick_y + 8,
                       fill="red", outline="darkred", width=2)
    
    # Draw line from center to stick
    canvas.create_line(x, y, stick_x, stick_y, fill="blue", width=2)


def draw_claw(canvas, x, y, size, claw_position):
    """Draw a claw control visualization.
    
    Args:
        canvas: tkinter Canvas widget
        x, y: center position
        size: size of the claw visualization
        claw_position: 0 (closed) to 1 (open)
    """
    # Draw claw base
    canvas.create_rectangle(x - size, y - size, x + size, y + size,
                           fill="lightblue", outline="black", width=2)
    
    # Draw progress bar for claw opening
    bar_width = 2 * size - 10
    bar_y = y + size - 10
    canvas.create_rectangle(x - size + 5, bar_y - 15, x + size - 5, bar_y,
                           fill="lightgray", outline="black", width=1)
    
    # Draw filled portion based on claw_position
    fill_width = bar_width * claw_position
    canvas.create_rectangle(x - size + 5, bar_y - 15, x - size + 5 + fill_width, bar_y,
                           fill="green", outline="darkgreen", width=1)
    
    # Draw text label
    canvas.create_text(x, y - 5, text=f"CLAW", font=("Arial", 12, "bold"), fill="black")
    canvas.create_text(x, y + 15, text=f"{claw_position:.2f}", font=("Arial", 10), fill="black")


def setup_gui(toggle_cal_callback, toggle_record_callback):
    """Set up the GUI and return all necessary components.
    
    Args:
        toggle_cal_callback: callback function for calibration toggle button
        toggle_record_callback: callback function for record toggle button
    
    Returns:
        tuple: (root, left_canvas, right_canvas, claw_canvas, status_label, rec_btn)
    """
    root = tk.Tk()
    root.title("ROV Dashboard")
    root.geometry("1000x600")

    # Top frame for control buttons
    top_frame = ttk.Frame(root)
    top_frame.pack(fill=tk.X, padx=5, pady=5)

    cal_btn = ttk.Button(top_frame, text="Toggle Calibration", command=toggle_cal_callback)
    cal_btn.pack(side=tk.LEFT, padx=5)

    rec_btn = ttk.Button(top_frame, text="Start Recording", command=toggle_record_callback)
    rec_btn.pack(side=tk.LEFT, padx=5)

    # Middle frame for controller visualizations
    middle_frame = ttk.Frame(root)
    middle_frame.pack(fill=tk.X, padx=5, pady=5)

    # Left joystick canvas
    left_frame = ttk.LabelFrame(middle_frame, text="Left Stick (Movement)")
    left_frame.pack(side=tk.LEFT, padx=5)
    
    left_canvas = tk.Canvas(left_frame, width=200, height=200, bg="white", highlightthickness=1)
    left_canvas.pack(padx=10, pady=10)

    # Right joystick canvas
    right_frame = ttk.LabelFrame(middle_frame, text="Right Stick (Look)")
    right_frame.pack(side=tk.LEFT, padx=5)
    
    right_canvas = tk.Canvas(right_frame, width=200, height=200, bg="white", highlightthickness=1)
    right_canvas.pack(padx=10, pady=10)

    # Claw canvas
    claw_frame = ttk.LabelFrame(middle_frame, text="Claw Control")
    claw_frame.pack(side=tk.LEFT, padx=5)
    
    claw_canvas = tk.Canvas(claw_frame, width=200, height=200, bg="white", highlightthickness=1)
    claw_canvas.pack(padx=10, pady=10)

    # Status frame (for future additions)
    status_frame = ttk.LabelFrame(root, text="Status")
    status_frame.pack(fill=tk.X, padx=5, pady=5)

    status_label = ttk.Label(status_frame, text="Ready", font=("Arial", 10))
    status_label.pack(padx=10, pady=5)

    return root, left_canvas, right_canvas, claw_canvas, status_label, rec_btn
