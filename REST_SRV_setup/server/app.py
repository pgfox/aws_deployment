from flask import Flask, jsonify, request

app = Flask(__name__)


@app.get("/")
def hello():
    return {"message": "Hello from Flask on EC2!"}


@app.get("/test_data")
def test_data():
    data_id = request.args.get("data_id")
    if data_id == "1":
        payload = {
            "id": "1",
            "name": "Alice Example",
            "address": "123 Cloud Lane, Internet City",
        }
    elif data_id == "2":
        payload = {
            "id": "2",
            "name": "Bob Sample",
            "address": "987 Server Way, Compute Town",
        }
    else:
        payload = {"error": "Unknown data_id", "data_id": data_id}
        return jsonify(payload), 404
    return jsonify(payload)
