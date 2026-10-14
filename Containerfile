FROM registry.access.redhat.com/ubi9/python-312:latest

# --------------------------------------------------------------------------------------------------
# set the working directory to /app
# --------------------------------------------------------------------------------------------------

WORKDIR /app

# --------------------------------------------------------------------------------------------------
# Copy manifest files and install python packages
# --------------------------------------------------------------------------------------------------

USER root
COPY pyproject.toml /app/pyproject.toml
RUN pip install uv \
    && uv venv \
    && uv pip install -r pyproject.toml
ENV VIRTUAL_ENV=/app/.venv
ENV PATH="/app/.venv/bin:$PATH"
USER default

# --------------------------------------------------------------------------------------------------
# copy source code and files
# --------------------------------------------------------------------------------------------------

COPY cli_schema_mcp /app/cli_schema_mcp
COPY clis /app/clis

# --------------------------------------------------------------------------------------------------
# Default: embed schemas from the build context (standard / CI build)
# For air-gapped OCI builds, replace the COPY below with the oras pull block instead:
#
#   RUN curl -sLO https://github.com/oras-project/oras/releases/download/v1.3.1/oras_1.3.1_linux_amd64.tar.gz \
#       && tar -xzf oras_1.3.1_linux_amd64.tar.gz oras \
#       && mv oras /usr/local/bin/oras \
#       && rm oras_1.3.1_linux_amd64.tar.gz \
#       && mkdir /tmp/schemas-pull \
#       && oras pull quay.io/takinosh/cli-schema-mcp:latest --output /tmp/schemas-pull \
#       && mkdir /app/schemas \
#       && tar -xzf /tmp/schemas-pull/schemas.tar.gz -C /app/schemas \
#       && rm -rf /tmp/schemas-pull
#   ENV SCHEMA_REGISTRY_PATH=/app/schemas
# --------------------------------------------------------------------------------------------------
COPY schemas /app/schemas

# --------------------------------------------------------------------------------------------------
# Set PYTHONPATH to include /app
# --------------------------------------------------------------------------------------------------

ENV PYTHONPATH=/app

EXPOSE 5001

# --------------------------------------------------------------------------------------------------
# add entrypoint for the container
# --------------------------------------------------------------------------------------------------

CMD ["/app/.venv/bin/python", "-m", "cli_schema_mcp.src.main"]
