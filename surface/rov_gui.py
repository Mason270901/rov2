import tkinter as tk
from tkinter import ttk

# GUI SETTINGS
###############################################################################
WINDOW_WIDTH = 1000
WINDOW_HEIGHT = 600

STICK_RADIUS = 80                           # radius of outermost gray circle
STICK_BOX    = 170                          # Size of the white box (around stick)
STICK_CENTER = STICK_BOX/2                  # Offset of the center of the gray circle within white box

CLAW_SIZE    = 50                           # size of blue box
CLAW_BOX     = 170                          # Size of the white box (around claw)
CLAW_CENTER  = CLAW_BOX/2                   # Offset of the blue claw box inside the white box

THRUSTER_BOX_W = 240                        # Width of the thruster panel canvas
THRUSTER_BOX_H = 170                        # Height of the thruster panel canvas
THRUSTER_LABELS = ["UL", "FL", "BL", "UR", "FR", "BR"]

def draw_joystick(canvas, lx, ly, deadzone):
    """Draw a joystick visualization on the canvas.
    
    Args:
        canvas: tkinter Canvas widget
        x, y: center position
        radius: size of the joystick circle
        lx, ly: normalized axis values (-1 to 1)
        deadzone: deadzone threshold (0 to 1)
    """
    radius = STICK_RADIUS
    x = y = STICK_CENTER

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


def draw_claw(canvas, claw_position):
    """Draw a claw control visualization.
    
    Args:
        canvas: tkinter Canvas widget
        x, y: center position
        size: size of the claw visualization
        claw_position: 0 (closed) to 1 (open)
    """

    size = CLAW_SIZE
    x = y = CLAW_CENTER

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


def draw_thrusters(canvas, thruster_values):
    """Draw 6 thruster progress bars on the canvas.

    Each bar is centred at zero and fills left (negative) or right (positive)
    proportional to the thruster value in [-1, 1].

    Args:
        canvas: tkinter Canvas widget
        thruster_values: list of 6 floats in [-1.0, 1.0]
    """
    bar_x_left  = 30    # left edge of bar track
    bar_x_right = THRUSTER_BOX_W - 10  # right edge of bar track
    bar_center  = (bar_x_left + bar_x_right) / 2
    bar_half    = (bar_x_right - bar_x_left) / 2
    bar_h       = 14    # height of each bar
    row_step    = (THRUSTER_BOX_H - 20) / len(THRUSTER_LABELS)  # vertical spacing

    for i, (label, val) in enumerate(zip(THRUSTER_LABELS, thruster_values)):
        y_mid = 18 + i * row_step
        y_top = y_mid - bar_h / 2
        y_bot = y_mid + bar_h / 2

        # Label
        canvas.create_text(bar_x_left - 5, y_mid, text=label,
                           anchor="e", font=("Arial", 8, "bold"), fill="black")

        # Background track
        canvas.create_rectangle(bar_x_left, y_top, bar_x_right, y_bot,
                                fill="#d0d0d0", outline="gray", width=1)

        # Filled portion (green)
        fill_w = abs(val) * bar_half
        if val >= 0:
            fx1, fx2 = bar_center, bar_center + fill_w
        else:
            fx1, fx2 = bar_center - fill_w, bar_center
        if fill_w > 0:
            canvas.create_rectangle(fx1, y_top + 1, fx2, y_bot - 1,
                                    fill="#00cc44", outline="", width=0)

        # Centre tick
        canvas.create_line(bar_center, y_top, bar_center, y_bot,
                           fill="black", width=1)

        # Value text
        canvas.create_text(bar_x_right + 4, y_mid, text=f"{val:+.2f}",
                           anchor="w", font=("Arial", 7), fill="#333333")


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
    root.geometry(f"{WINDOW_WIDTH}x{WINDOW_HEIGHT}")

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
    
    left_canvas = tk.Canvas(left_frame, width=STICK_BOX, height=STICK_BOX, bg="white", highlightthickness=1)
    left_canvas.pack(padx=10, pady=10)

    # Right joystick canvas
    right_frame = ttk.LabelFrame(middle_frame, text="Right Stick (Look)")
    right_frame.pack(side=tk.LEFT, padx=5)
    
    right_canvas = tk.Canvas(right_frame, width=STICK_BOX, height=STICK_BOX, bg="white", highlightthickness=1)
    right_canvas.pack(padx=10, pady=10)

    # Claw canvas
    claw_frame = ttk.LabelFrame(middle_frame, text="Claw Control")
    claw_frame.pack(side=tk.LEFT, padx=5)
    
    claw_canvas = tk.Canvas(claw_frame, width=CLAW_BOX, height=CLAW_BOX, bg="white", highlightthickness=1)
    claw_canvas.pack(padx=10, pady=10)

    # Thrusters canvas
    thruster_frame = ttk.LabelFrame(middle_frame, text="Thrusters")
    thruster_frame.pack(side=tk.LEFT, padx=5)

    thruster_canvas = tk.Canvas(thruster_frame, width=THRUSTER_BOX_W, height=THRUSTER_BOX_H,
                                bg="white", highlightthickness=1)
    thruster_canvas.pack(padx=10, pady=10)

    # Status frame (for future additions)
    status_frame = ttk.LabelFrame(root, text="Status")
    status_frame.pack(fill=tk.X, padx=5, pady=5)

    status_label = ttk.Label(status_frame, text="Ready", font=("Arial", 10))
    status_label.pack(padx=10, pady=5)

    return root, left_canvas, right_canvas, claw_canvas, thruster_canvas, status_label, rec_btn
