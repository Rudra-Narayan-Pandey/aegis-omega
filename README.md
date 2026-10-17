# 🛡️ Aegis Omega: Zero-Trust eBPF Gateway

[![Kubernetes](https://img.shields.io/badge/kubernetes-%23326ce5.svg?style=for-the-badge&logo=kubernetes&logoColor=white)](https://kubernetes.io/)
[![Cilium](https://img.shields.io/badge/cilium-%23FBEF2E.svg?style=for-the-badge&logo=cilium&logoColor=black)](https://cilium.io/)
[![Envoy](https://img.shields.io/badge/envoy-%232D31A4.svg?style=for-the-badge&logo=envoyproxy&logoColor=white)](https://www.envoyproxy.io/)
[![Go](https://img.shields.io/badge/go-%2300ADD8.svg?style=for-the-badge&logo=go&logoColor=white)](https://go.dev/)

**Aegis Omega** is a highly secure, cloud-native gateway architecture engineered to enforce true **Zero-Trust** microservice communication at the Linux kernel level. 

Moving beyond traditional Layer 3/Layer 4 `iptables` firewalls, this project leverages **Cilium eBPF** and **Envoy Proxy** to implement strict Layer 7 (HTTP) network policy enforcement. It programmatically drops unauthorized API access attempts at the socket layer before they consume application resources, guaranteeing that microservices are only accessed via explicitly whitelisted URIs.

---

## 📑 Table of Contents

1. [Microservice Security Paradigm](#-microservice-security-paradigm)
2. [Architecture & Deep Security Design](#-architecture--deep-security-design)
3. [Environment Prerequisites](#-environment-prerequisites)
4. [Detailed Deployment Guide](#-detailed-deployment-guide)
5. [Validation & Penetration Testing](#-validation--penetration-testing)
6. [Observability with Hubble UI](#-observability-with-hubble-ui)
7. [Troubleshooting](#-troubleshooting)
8. [GitHub Deployment](#-github-deployment)

---

## 🔬 Microservice Security Paradigm

In legacy Kubernetes networking (relying on `kube-proxy` and `iptables`), policies are limited to IP addresses and ports. This presents a massive attack surface: if an attacker breaches the network perimeter, they can traverse any exposed HTTP endpoint within the cluster.

**Aegis Omega** intercepts traffic directly in the Linux Kernel using **eBPF (Extended Berkeley Packet Filter)**. When combined with Cilium's Envoy sidecar integration, traffic is parsed at the application layer (L7). This allows us to define security rules based on exact HTTP methods (`GET`, `POST`) and paths (`/health`, `/api/v1/secret`), establishing a true Zero-Trust interior.

---

## 🏗️ Architecture & Deep Security Design

### Traffic Flow & Kernel Hooking Diagram

```text
[ External Client / Attacker ] 
           │
           ▼ (HTTP GET Request)
┌─────────────────────────────────────────────────────────────────────────┐
│ Kubernetes Node (k3d-aegis-cluster-server-0)                            │
│                                                                         │
│  [ Kernel Space - eBPF ]                                                │
│  ┌───────────────────────────────────────────────────────────────────┐  │
│  │ Cilium eBPF Socket Filter                                         │  │
│  │ Intercepts packet, maps to CiliumNetworkPolicy, routes to Envoy   │  │
│  └──────────────────────────┬────────────────────────────────────────┘  │
│                             │                                           │
│  [ User Space ]             ▼                                           │
│  ┌───────────────────────────────────────────────────────────────────┐  │
│  │ Envoy L7 Proxy (Cilium Managed)                                   │  │
│  │  ├── 🟢 Match: GET /health        ──► Forward to Pod (HTTP 200)   │  │
│  │  └── 🔴 Match: GET /api/v1/secret ──► Drop at proxy (HTTP 403)    │  │
│  └──────────────────────────┬────────────────────────────────────────┘  │
│                             │                                           │
│                             ▼ (Only Validated, Clean Traffic Arrives)   │
│  ┌───────────────────────────────────────────────────────────────────┐  │
│  │ [ aegis-gateway Pod ]                                             │  │
│  │ Go Binary | User: 1000 | Read-Only Root FS | Dropped Capabilities   │  │
│  └───────────────────────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────────────────┘
```

### Triple-Tiered Hardening Strategy

1. **Network Layer (eBPF + Envoy)**: Complete bypass of `iptables`. Traffic parsing ensures only compliant HTTP requests proceed.
2. **Pod Security Context**: The application container is stripped of privileges.
   * `runAsNonRoot: true` / `runAsUser: 1000` ensures a container breakout yields zero host privileges.
   * `readOnlyRootFilesystem: true` prevents malware from writing to disk. Temporary writes are restricted to an isolated `emptyDir` mounted at `/tmp`.
   * `capabilities: { drop: ["ALL"] }` removes kernel capabilities like `CAP_NET_RAW` or `CAP_SYS_ADMIN`.
3. **Infrastructure Abstraction**: Running within nested Docker containers (`k3d`) provides an isolated sandbox for testing complex kernel behaviors without risking host system stability.

---

## ⚙️ Environment Prerequisites

Ensure your development environment has the following tools installed and configured:

* **Docker**: Required for `k3d` (nested containerization). Ensure adequate CPU/Memory allocation.
* **kubectl**: Kubernetes command-line tool.
* **Helm**: Package manager for Kubernetes deployments.
* **k3d**: Lightweight Kubernetes running in Docker.
* **Cilium CLI**: Essential for installing, managing, and validating the mesh status. *(Targeting v1.20.1+)*

---

## 🚀 Detailed Deployment Guide

This setup utilizes `k3d` to emulate a production Kubernetes environment locally, requiring specific flag configurations to support eBPF filesystems.

### 1. Provision the Kubernetes Cluster

We must explicitly disable k3s's default `flannel` CNI and network policy controllers. This provides a blank canvas for Cilium to take absolute control over the networking stack.

```bash
k3d cluster create aegis-cluster \
  --k3s-arg "--flannel-backend=none@server:*" \
  --k3s-arg "--disable-network-policy@server:*"
```

### 2. Mount eBPF and CGroupv2 Filesystems (k3d Specific)

Because `k3d` runs Kubernetes nodes as Docker containers, Cilium cannot automatically mount the host's eBPF filesystem. We must manually share the `bpffs` and `cgroup2` mounts inside the server node to prevent the Cilium agents from entering a `CrashLoopBackOff`.

```bash
docker exec k3d-aegis-cluster-server-0 mount bpffs /sys/fs/bpf -t bpf
docker exec k3d-aegis-cluster-server-0 mount --make-shared /sys/fs/bpf
docker exec k3d-aegis-cluster-server-0 mkdir -p /run/cilium/cgroupv2
docker exec k3d-aegis-cluster-server-0 mount -t cgroup2 none /run/cilium/cgroupv2
docker exec k3d-aegis-cluster-server-0 mount --make-shared /run/cilium/cgroupv2
```

### 3. Install the Cilium Service Mesh

Install Cilium via its CLI. We pass critical `set` flags to accommodate the single-node `k3d` topology:
* `k8sServiceHost`: Forces Cilium to talk directly to the internal API on loopback, avoiding external port mapping conflicts.
* `kubeProxyReplacement=false`: k3s embeds kube-proxy; this prevents Cilium from attempting an unsupported aggressive takeover.
* `cgroup.autoMount.enabled=false`: Acknowledges our manual mounts from Step 2.

```bash
cilium install \
  --set k8sServiceHost=127.0.0.1 \
  --set k8sServicePort=6443 \
  --set operator.replicas=1 \
  --set kubeProxyReplacement=false \
  --set cgroup.autoMount.enabled=false

# Wait for all Cilium DaemonSets and Envoy proxies to transition to 1/1 Running
cilium status --wait
```

### 4. Deploy the Gateway & Security Policies

With the mesh healthy, we inject our application and the zero-trust policy.

```bash
# 1. Import your locally built image into the k3d internal registry
k3d image import aegis-gateway:latest -c aegis-cluster

# 2. Deploy the application and expose the ClusterIP service
kubectl apply -f k8s/aegis-gateway.yaml
kubectl expose deployment aegis-gateway --port=8000 --target-port=8000 --type=ClusterIP

# 3. Apply the eBPF Layer 7 Zero-Trust Policy
kubectl apply -f k8s/cilium-ebpf-policy.yaml
```

---

## 🧪 Validation & Penetration Testing

With the system running, we simulate internal cluster traffic to prove the L7 policies are actively parsing and filtering requests. We use an ephemeral Alpine pod to run `curl` commands.

### Test 1: Authorized Traffic (`/health`)

Verify that authorized paths pass through the Envoy proxy successfully.

```bash
kubectl run test-client --rm -i --tty --image=alpine -- sh -c "apk add --no-cache curl && curl -v -s -X GET http://aegis-gateway:8000/health"
```

**Expected Outcome**: 
The connection succeeds. Even if the application logic returns a `404 Not Found` for the specific path, the HTTP headers will reveal `< server: envoy`, confirming the proxy allowed the traffic to reach the destination container.

### Test 2: Unauthorized Traffic (`/api/v1/secret`)

Verify that unauthorized paths are dropped instantaneously.

```bash
kubectl run test-client-blocked --rm -i --tty --image=alpine -- sh -c "apk add --no-cache curl && curl -m 5 -v -s -X GET http://aegis-gateway:8000/api/v1/secret"
```

**Expected Outcome**: 
The mesh network recognizes the prohibited URI and actively rejects the packet on behalf of the application. The container never sees this traffic.
```http
< HTTP/1.1 403 Forbidden
< server: envoy

Access denied
```

---

## 👁️ Observability with Hubble UI

Aegis Omega integrates seamlessly with **Hubble**, Cilium's observability platform. It provides real-time visual telemetry, service dependency mapping, and granular flow logs.

**1. Enable Hubble UI Components:**
```bash
cilium hubble enable --ui
```

**2. Launch the Dashboard:**
```bash
cilium hubble ui
```
*This establishes a local port-forward. Open `http://127.0.0.1:12000` in your web browser. Ensure you switch the namespace filter in the top left from `cilium-secrets` to `default`. Re-run the test queries above to watch the topographical map dynamically draw green (forwarded) and red (dropped) traffic lines!*

---

## 🔧 Troubleshooting

**1. Pods stuck in `Pending` or `CrashLoopBackOff`**
*   **Cause**: Docker Desktop/Codespace lacks sufficient memory, OR the eBPF filesystem mounts failed.
*   **Fix**: Ensure you ran the manual `docker exec` mount commands *before* running `cilium install`. 

**2. Unable to reinstall Cilium: namespace `cilium-secrets` is terminating**
*   **Cause**: A previous failed installation left a finalizer blocking namespace deletion.
*   **Fix**: Force the finalizer removal via the Kubernetes API:
    ```bash
    kubectl get namespace cilium-secrets -o json | tr -d "\n" | sed 's/"finalizers": \[[^]]\+\]/"finalizers": []/' | kubectl replace --raw /api/v1/namespaces/cilium-secrets/finalize -f -
    ```

---

## 💻 GitHub Deployment

To push this completed architecture to your repository, execute the following from the project root:

```bash
git init
git add .
git commit -m "feat: complete zero-trust gateway with cilium ebpf l7 policy and hubble observability"
git branch -M main
git remote add origin https://github.com/Rudra-Narayan-Pandey/aegis-omega.git
git push -u origin main
```

---
*Architected and developed by [Rudra Narayan Pandey](https://github.com/Rudra-Narayan-Pandey)*
