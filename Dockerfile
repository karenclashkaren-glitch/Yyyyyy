FROM alpine:3.20

RUN apk add --no-cache curl jq tar gzip bash gettext ca-certificates nginx python3

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
COPY nginx.conf.template /app/nginx.conf.template
COPY panel/ /app/panel/
COPY start.sh /app/start.sh
RUN chmod +x /app/start.sh

# Defaults; override any of these as Railway service variables
ENV WSPATH=/vless
ENV PANEL_USERNAME=admin

# Railway injects PORT at runtime; nginx is the only process bound to it.
# sing-box and the panel both listen on localhost-only internal ports.
EXPOSE 8080

ENTRYPOINT ["/app/start.sh"]
