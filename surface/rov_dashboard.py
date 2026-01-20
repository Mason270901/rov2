import socket, json, threading, subprocess, signal
from inputs import get_gamepad
import tkinter as tk
from tkinter import ttk

PI5_IP = "10.0.0.204"
PI5_PORT = 9000

DEADZONE = 0.15

sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)

axes = {"LX":0,"LY":0,"RX":0,"RY":0,"LT":0,"RT":0}
calibrate = False
recording = False
record_proc = None

# 16 bit normalize
def norm(v): return max(-1,min(1,v/32767))

# call this after norm
def deadzone(v):
    if(abs(v) <= DEADZONE):
        return 0
    else:
        return v

# handles each xbox input
def process(e):
    if e.ev_type=="Absolute":
        if e.code=="ABS_X": axes["LX"]=deadzone(norm(e.state))
        if e.code=="ABS_Y": axes["LY"]=deadzone(-norm(e.state))
        if e.code=="ABS_RX": axes["RX"]=deadzone(norm(e.state))
        if e.code=="ABS_RY": axes["RY"]=deadzone(-norm(e.state))
        if e.code=="ABS_Z": axes["LT"]=e.state/255
        if e.code=="ABS_RZ": axes["RT"]=e.state/255

# takes the axes object, and converts it to a format to send over the wire
def compute():
    claw = 0.5 + 0.5*(axes["RT"]-axes["LT"])
    claw = max(0,min(1,claw))
    return {
        "surge": axes["LY"],
        "sway": axes["LX"],
        "yaw": axes["RX"],
        "heave": axes["RY"],
        "claw_pos": claw,
        "calibrate": calibrate
    }

def fmt(c):
    return (
        f"SURGE {c['surge']:.3f} "
        f"SWAY {c['sway']:.3f} "
        f"YAW {c['yaw']:.3f} "
        f"HEAVE {c['heave']:.3f} "
        f"CLAW_POS {c['claw_pos']:.3f} "
        f"CALIBRATE {int(c['calibrate'])}\n"
    )

def sender():
    while True:
        for e in get_gamepad():
            process(e)
        # print(axes)
        sock.sendto(fmt(compute()).encode(), (PI5_IP, PI5_PORT))

threading.Thread(target=sender, daemon=True).start()

def toggle_cal():
    global calibrate
    calibrate = not calibrate

def toggle_record():
    global recording, record_proc
    if not recording:
        record_proc = subprocess.Popen([
            "gst-launch-1.0",
            "udpsrc", "port=5000",
            "!", "application/x-rtp, media=video, encoding-name=H264, payload=96",
            "!", "rtph264depay",
            "!", "h264parse",
            "!", "mp4mux",
            "!", "filesink", "location=rov_recording.mp4"
        ])
        recording = True
        rec_btn.config(text="Stop Recording")
    else:
        record_proc.terminate()
        recording = False
        rec_btn.config(text="Start Recording")

root = tk.Tk()
root.title("ROV Dashboard")

cal_btn = ttk.Button(root, text="Toggle Calibration", command=toggle_cal)
cal_btn.pack()

rec_btn = ttk.Button(root, text="Start Recording", command=toggle_record)
rec_btn.pack()

# handle terminal Ctrl+C (SIGINT) so the Tk mainloop exits cleanly
def _sigint_handler(signum, frame=None):
    print('caught ^C')
    global recording, record_proc
    try:
        if record_proc is not None and recording:
            record_proc.terminate()
    except Exception:
        pass
    try:
        root.destroy()
    except Exception:
        pass

def _check():
    # schedule another check so the signal gets processed while
    # the Tk event loop is running
    root.after(500, _check)

# register the signal handler and start the periodic check
signal.signal(signal.SIGINT, _sigint_handler)
root.after(500, _check)
root.bind_all('<Control-c>', lambda e: _sigint_handler(None, None))

root.mainloop()
