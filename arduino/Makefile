.PHONY: program compile monitor

compile:
	arduino-cli compile --fqbn arduino:avr:mega .

program: compile
	arduino-cli upload -p /dev/ttyACM1 --fqbn arduino:avr:mega .

monitor:
	arduino-cli monitor -p /dev/ttyACM1 -c baudrate=115200
