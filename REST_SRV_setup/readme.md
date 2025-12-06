# REST Service Setup

This directory provisions a lightweight REST service on EC2 for networking tests. It contains:

- `create_REST.py`: builds the server infrastructure (key pair, security group, EC2 instance).
- `server/app.py`: Flask application served via Gunicorn and fronted by Nginx.
- `client/query_test_data.py`: simple client to query the `/test_data` endpoint.

## Server

`create_REST.py` launches a `t3.micro` instance (Ubuntu 20.04) into the public subnet of a given VPC (identified by the `Tier=public` tag). The assumption is a vpc has been created that has a publicly
accessible subnet that has been taged with `Tier=public`. User data:

1. Installs Python, Flask, Gunicorn, and Nginx.
2. Copies the local `server/app.py` to `/opt/rest_app/app.py`.
3. Creates a systemd unit that runs Gunicorn (`app:app`) behind a Unix socket.
4. Configures Nginx to proxy port 80 to Gunicorn, providing proper request buffering and TLS termination options later.

This architecture decouples the WSGI app (Flask) from the web server (Nginx), improving performance, security, and flexibility when comparing to running Flask’s built-in server.

Resources created in AWS:

- Key pair (`pf1-rest-key` by default) and local PEM file.
- Security group (`pf1-rest-sg`) allowing inbound SSH (22/tcp) and HTTP (80/tcp).
- EC2 instance (`pf1-rest-instance`) with a public IP, launched into the VPC’s public subnet.

### Usage

```bash
source .venv/bin/activate
python REST_SRV_setup/create_REST.py --vpc-id vpc-0123456789abcdef0
```

After the instance reaches `running`, curl the public IP:

```bash
curl http://203.0.113.10/
curl "http://203.0.113.10/test_data?data_id=1"
```

## Client

`client/query_test_data.py` is a minimal script that calls the `/test_data` endpoint and prints the JSON response. It helps validate connectivity without hand-writing curl commands.

### Usage

```bash
source .venv/bin/activate
python REST_SRV_setup/client/query_test_data.py \
  --server-ip 203.0.113.10 \
  --data-id 2
```

Replace `203.0.113.10` with the instance’s public IP. The script defaults to `data_id=1` if omitted.
