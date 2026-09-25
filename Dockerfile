FROM alpine:3.20

RUN apk add --no-cache curl jq tar gzip bash gettext ca-certificates

# Fetch and install the latest sing-box release for the container's architecture
RUN set -eux; \
    ARCH="$(uname -m)"; \
    case "$ARCH" in \
        x86_64) SBARCH=amd64 ;; \
        aarch64) SBARCH=arm64 ;; \
        *) echo "Unsupported architecture: $ARCH" && exit 1 ;; \
    esac; \
    VERSION="$(curl -fsSL https://api.github.com/repos/SagerNet/sing-box/releases/latest | jq -r .tag_name | sed 's/^v//')"; \
    echo "Installing sing-box v${VERSION} (${SBARCH})"; \
    curl -fsSL -o /tmp/sing-box.tar.gz \
        "https://github.com/SagerNet/sing-box/releases/download/v${VERSION}/sing-box-${VERSION}-linux-${SBARCH}.tar.gz"; \
    tar -xzf /tmp/sing-box.tar.gz -C /tmp; \
    mv "/tmp/sing-box-${VERSION}-linux-${SBARCH}/sing-box" /usr/local/bin/sing-box; \
    chmod +x /usr/local/bin/sing-box; \
    rm -rf /tmp/sing-box.tar.gz "/tmp/sing-box-${VERSION}-linux-${SBARCH}"

WORKDIR /app
COPY config.json.template /app/config.json.template
COPY entrypoint.sh /app/entrypoint.sh
RUN chmod +x /app/entrypoint.sh

# Default WebSocket path; override with a WSPATH env var in Railway if you want
ENV WSPATH=/vless

# Railway injects PORT at runtime and routes its public HTTPS domain to it
EXPOSE 8080

ENTRYPOINT ["/app/entrypoint.sh"]
