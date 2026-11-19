from flask import Flask, render_template, request, jsonify
from netmiko import ConnectHandler
from netmiko.exceptions import NetmikoTimeoutException, NetmikoAuthenticationException
from inventory import devices

app = Flask(__name__)


@app.route("/", methods=["GET"])
def index():
    device_list = [
        {
            "name": name,
            "host": details["host"],
            "device_type": details["device_type"],
        }
        for name, details in devices.items()
    ]
    return render_template("index.html", devices=device_list)


@app.route("/run", methods=["POST"])
def run_automation():
    data = request.get_json()
    selected_devices = data.get("devices", [])
    command_type = data.get("command_type", "show")
    raw_commands = data.get("commands", "")

    commands = [line.strip() for line in raw_commands.splitlines() if line.strip()]

    if not selected_devices:
        return jsonify({"error": "Please select at least one device."}), 400
    if not commands:
        return jsonify({"error": "Please enter at least one command."}), 400

    results = []

    for dev_name in selected_devices:
        device_params = devices.get(dev_name)
        if not device_params:
            results.append({
                "device": dev_name,
                "host": "Unknown",
                "status": "error",
                "output": "Device not found in inventory.py",
            })
            continue

        try:
            with ConnectHandler(**device_params) as net_connect:
                if device_params.get("secret"):
                    net_connect.enable()

                if command_type == "config":
                    output = net_connect.send_config_set(commands)
                else:
                    cmd_outputs = []
                    for cmd in commands:
                        res = net_connect.send_command(cmd)
                        cmd_outputs.append(f"--- {cmd} ---\n{res}")
                    output = "\n\n".join(cmd_outputs)

                results.append({
                    "device": dev_name,
                    "host": device_params["host"],
                    "status": "success",
                    "output": output,
                })

        except NetmikoAuthenticationException:
            results.append({
                "device": dev_name,
                "host": device_params["host"],
                "status": "error",
                "output": "Authentication failed. Check username, password, or enable secret.",
            })
        except NetmikoTimeoutException:
            results.append({
                "device": dev_name,
                "host": device_params["host"],
                "status": "error",
                "output": "Connection timed out. Verify IP reachability and Telnet/SSH access.",
            })
        except Exception as exc:
            results.append({
                "device": dev_name,
                "host": device_params["host"],
                "status": "error",
                "output": f"Unexpected error: {str(exc)}",
            })

    return jsonify({"results": results})


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=True)