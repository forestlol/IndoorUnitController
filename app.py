from flask import Flask, request, jsonify
from flask_restx import Api, Resource, fields
import paho.mqtt.client as mqtt
import base64
import json
import warnings

# Suppress specific deprecation warnings
warnings.filterwarnings("ignore", category=DeprecationWarning)

# MQTT Broker details
broker = "152.42.161.80"
port = 1883  # Port for MQTT over TLS

app = Flask(__name__)
api = Api(app, version='1.0', title='Indoor Unit Controller API',
          description='An API to control indoor unit switches')

# Namespaces for different products
ns_ws503 = api.namespace('ws503', description='Operations related to WS503 control')
ns_ws558 = api.namespace('ws558', description='Operations related to WS558 control')
ns_ws156 = api.namespace('ws156', description='Operations related to WS156 control')

# Request models
switch_model_ws503 = api.model('SwitchStateWS503', {
    'device_eui': fields.String(required=True, description='Device EUI'),
    'switch_states': fields.List(fields.Integer, required=True, description='List of switch states (0 for off, 1 for on)')
})

switch_model_ws558 = api.model('SwitchStateWS558', {
    'device_eui': fields.String(required=True, description='Device EUI'),
    'switch_states': fields.List(fields.Integer, required=True, description='List of switch states (0 for off, 1 for on)')
})

button_model_ws156 = api.model('ButtonStateWS156', {
    'device_eui': fields.String(required=True, description='Device EUI'),
    'button_id': fields.Integer(required=True, description='Button ID (1-6)')
})

def send_command_base64(command_hex, device_eui):
    client = mqtt.Client(protocol=mqtt.MQTTv311)
    client.connect(broker, port, 60)
    client.loop_start()

    # Convert hex command to Base64
    command_bytes = bytes.fromhex(command_hex)
    command_base64 = base64.b64encode(command_bytes).decode('ascii')

    # Create payload in JSON format
    payload = {
        "confirmed": True,
        "fport": 85,
        "data": command_base64
    }

    # Convert payload to JSON string
    payload_json = json.dumps(payload)
    
    # Print the payload for verification
    print("Payload JSON:", payload_json)

    # Publish the message to the topic specific to the device EUI
    topic = f"downlink/{device_eui}"
    result = client.publish(topic, payload_json)
    
    # Print result for debugging
    print("Publish result:", result)
    if result.rc != mqtt.MQTT_ERR_SUCCESS:
        print(f"Failed to publish message: {result.rc}")
    else:
        print("Message published successfully")

    client.loop_stop()
    client.disconnect()

def calculate_byte1_ws503(switch_states):
    # Calculate byte1 based on switch states for WS503
    byte1 = 0b00010000  # Bit 4 to allow control
    if switch_states[0] == 1:
        byte1 |= 0b00000001  # Set Bit 0 to turn on switch 1
    return format(byte1, '02X')

def calculate_byte1_ws558(switch_states):
    # Calculate byte1 based on switch states for WS558
    byte2 = 0
    for i, state in enumerate(switch_states):
        if state == 1:
            byte2 |= (1 << i)
    return f"{byte2:02X}"

def calculate_command_ws156(button_id):
    # Button ID (1-6) to Byte 1 value for WS156
    button_map = {
        1: '01',
        2: '02',
        3: '03',
        4: '04',
        5: '05',
        6: '06'
    }
    if button_id not in button_map:
        raise ValueError("Invalid button ID. Must be between 1 and 6.")
    
    byte1 = '34'  # Fixed value for WS156
    byte2 = button_map[button_id]
    byte3 = '01'  # Short press, double press
    byte4 = '00'  # Short press trigger
    
    return f"ff{byte1}{byte2}{byte3}{byte4}"

@ns_ws503.route('/')
class WS503Controller(Resource):
    @ns_ws503.expect(switch_model_ws503)
    @ns_ws503.response(200, 'Command sent successfully')
    @ns_ws503.response(400, 'Invalid input')
    @ns_ws503.response(500, 'Internal server error')
    def post(self):
        """
        Control WS503 switches
        """
        try:
            # Get device EUI and switch states from the request
            device_eui = request.json.get('device_eui')
            switch_states = request.json.get('switch_states')
            
            if not device_eui:
                return {"error": "Device EUI is required."}, 400
            if not switch_states or len(switch_states) != 3:
                return {"error": "Invalid switch states. Must provide exactly 3 states."}, 400
            
            # Calculate byte1
            byte1 = calculate_byte1_ws503(switch_states)
            command_hex = f"08{byte1}ff"

            # Send command
            send_command_base64(command_hex, device_eui)
            
            return {"message": "Command sent successfully", "command_hex": command_hex}, 200

        except Exception as e:
            return {"error": str(e)}, 500

@ns_ws558.route('/')
class WS558Controller(Resource):
    @ns_ws558.expect(switch_model_ws558)
    @ns_ws558.response(200, 'Command sent successfully')
    @ns_ws558.response(400, 'Invalid input')
    @ns_ws558.response(500, 'Internal server error')
    def post(self):
        """
        Control WS558 switches
        """
        try:
            # Get device EUI and switch states from the request
            device_eui = request.json.get('device_eui')
            switch_states = request.json.get('switch_states')
            
            if not device_eui:
                return {"error": "Device EUI is required."}, 400
            if not switch_states or len(switch_states) != 8:
                return {"error": "Invalid switch states. Must provide exactly 8 states."}, 400
            
            # Calculate byte1
            byte1 = calculate_byte1_ws558(switch_states)
            command_hex = f"08ff{byte1}"

            # Send command
            send_command_base64(command_hex, device_eui)
            
            return {"message": "Command sent successfully", "command_hex": command_hex}, 200

        except Exception as e:
            return {"error": str(e)}, 500

@ns_ws156.route('/')
class WS156Controller(Resource):
    @ns_ws156.expect(button_model_ws156)
    @ns_ws156.response(200, 'Command sent successfully')
    @ns_ws156.response(400, 'Invalid input')
    @ns_ws156.response(500, 'Internal server error')
    def post(self):
        """
        Control WS156 buttons
        """
        try:
            # Get device EUI and button ID from the request
            device_eui = request.json.get('device_eui')
            button_id = request.json.get('button_id')
            
            if not device_eui:
                return {"error": "Device EUI is required."}, 400
            if not button_id or not (1 <= button_id <= 6):
                return {"error": "Invalid button ID. Must be between 1 and 6."}, 400
            
            # Calculate command
            command_hex = calculate_command_ws156(button_id)

            # Send command
            send_command_base64(command_hex, device_eui)
            
            return {"message": "Command sent successfully", "command_hex": command_hex}, 200

        except Exception as e:
            return {"error": str(e)}, 500

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=4000)
