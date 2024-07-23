from flask import Flask, request, jsonify
from flask_restx import Api, Resource, fields
import paho.mqtt.client as mqtt
import base64
import json
import warnings

# Suppress specific deprecation warnings
warnings.filterwarnings("ignore", category=DeprecationWarning)

# MQTT Broker details
broker = "5da2d544808e4e6d95107a22fdd8234f.s1.eu.hivemq.cloud"
port = 8883  # Port for MQTT over TLS
username = "admin"
password = "password"
topic = "downlink/classroom/24E124756E049153"
use_ssl = True

app = Flask(__name__)
api = Api(app, version='1.0', title='Indoor Unit Controller API',
          description='An API to control indoor unit switches')
ns = api.namespace('indoor-unit-controller', description='Operations related to indoor unit control')

switch_model = api.model('SwitchState', {
    'switch_states': fields.List(fields.Integer, required=True, description='List of switch states (0 for off, 1 for on)')
})

def send_command_base64(command_hex):
    client = mqtt.Client(protocol=mqtt.MQTTv311)
    client.username_pw_set(username, password)
    if use_ssl:
        client.tls_set()
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

    result = client.publish(topic, payload_json)
    
    # Print result for debugging
    print("Publish result:", result)
    if result.rc != mqtt.MQTT_ERR_SUCCESS:
        print(f"Failed to publish message: {result.rc}")
    else:
        print("Message published successfully")

    client.loop_stop()
    client.disconnect()

def calculate_byte2(switch_states):
    if len(switch_states) != 8:
        raise ValueError("There must be exactly 8 switch states.")
    
    binary_string = ''.join(str(state) for state in reversed(switch_states))
    byte_value = int(binary_string, 2)
    return format(byte_value, '02X')

@ns.route('/')
class IndoorUnitController(Resource):
    @ns.expect(switch_model)
    @ns.response(200, 'Command sent successfully')
    @ns.response(400, 'Invalid input')
    @ns.response(500, 'Internal server error')
    def post(self):
        """
        Control indoor unit switches
        """
        try:
            # Get switch states from the request
            switch_states = request.json.get('switch_states')
            
            if not switch_states or len(switch_states) != 8:
                return {"error": "Invalid switch states. Must provide exactly 8 states."}, 400
            
            # Calculate byte2
            byte2 = calculate_byte2(switch_states)
            command_hex = f"08FF{byte2}"

            # Send command
            send_command_base64(command_hex)
            
            return {"message": "Command sent successfully", "command_hex": command_hex}, 200

        except Exception as e:
            return {"error": str(e)}, 500

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)
