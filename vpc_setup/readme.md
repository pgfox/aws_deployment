# VPC Setup Summary

The `create_vpc.py` script provisions the following AWS networking resources in the specified region:

- A VPC (`pf1-vpc`) with DNS support/hostnames enabled.
- An Internet Gateway (`pf1-igw`) attached to the VPC.
- Two subnets:
  - `pf1-subnet-1` tagged `Tier=public`.
  - `pf1-subnet-2` tagged `Tier=private`.
- A route table (`pf1-public-rt`) associated with the public subnet.
- A security group (`pf1-public-sg`) that allows inbound SSH/HTTP/HTTPS from anywhere.

## Public Subnet Components

`pf1-subnet-1` becomes a public subnet through the combination of:

1. `MapPublicIpOnLaunch=True` so instances obtain public IPv4 addresses automatically.
2. Association with `pf1-public-rt`, which contains a `0.0.0.0/0` route to the Internet Gateway.
3. Association of workloads with `pf1-public-sg`, which opens the necessary inbound ports.

All three elements are required for resources in `pf1-subnet-1` to be reachable from the internet. Instances placed in `pf1-subnet-2` remain private unless you add additional routing and security rules.
