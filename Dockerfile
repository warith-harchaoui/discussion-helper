# ============================================================
# discussion-helper — the loop, served.
#
#   docker compose up -d
#   curl -s localhost:8090/health
#
# What this image is, and is not
# ------------------------------
# It serves the **remote** transport: a browser or a phone line opens a
# session, streams audio frames in over the WebSocket, and gets the agent's
# audio back. That is the half of this package a container can honestly run.
#
# It does **not** open a microphone. `--transport local` reads the machine's
# sound card through capture-helper, and a container has no sound card —
# passing one through means `--device /dev/snd` on Linux and nothing at all on
# macOS or Windows, which is a per-machine arrangement and not an image.
# Installing the `listen` extra here would put a microphone client in the
# image that cannot find a microphone, so the extra is left out and the
# refusal happens at install time rather than at the first call.
# ============================================================
FROM python:3.11-slim

# espeak-ng: speaker-helper phonemises Kokoro through it, as a separate binary
# reached by ctypes. The `espeakng-loader` wheel carries its own copy and that
# copy is the fallback, not the plan — it was built on a CI runner and
# resolves its data to that machine's home directory. libsndfile backs the
# `soundfile` wheel that decodes the audio.
RUN apt-get update && apt-get install -y --no-install-recommends \
        espeak-ng \
        libsndfile1 \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Dependencies first, for layer caching.
COPY pyproject.toml README.md ./
COPY discussion_helper ./discussion_helper

# `speak` and `think` but not `listen` or `play`: the voice and the answer are
# this container's job, the microphone and the sound card are the caller's.
RUN pip install --no-cache-dir ".[speak,think,server,mcp]"

# The voice weights, fetched at build time rather than on the first request.
# An image that downloads 340 MB the first time somebody calls it is an image
# whose first call times out — and every replica downloads it again.
RUN speaker-helper install-voice --engine kokoro

ENV DISCUSSION_HELPER_MCP_HOST=0.0.0.0 \
    DISCUSSION_HELPER_MCP_PORT=8090 \
    LOG_LEVEL=info

EXPOSE 8090

# The MCP entry point serves the HTTP API *and* mounts the agent tools on the
# same app, so one command gives both surfaces. There is no second process.
CMD ["discussion-helper-mcp", "--host", "0.0.0.0", "--port", "8090"]
