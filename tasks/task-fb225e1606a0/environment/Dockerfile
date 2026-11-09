FROM public.ecr.aws/docker/library/python:3.13-slim-bookworm@sha256:01f42367a0a94ad4bc17111776fd66e3500c1d87c15bbd6055b7371d39c124fb
COPY vendor /opt/tbench-public-setup
RUN cd /opt/tbench-public-setup \
 && sha256sum -c SHA256SUMS \
 && dpkg -i ./*.deb \
 && python3 -m pip install --no-index --no-deps asciinema-2.4.0-py3-none-any.whl \
 && tmux -V && asciinema --version \
 && rm -rf /opt/tbench-public-setup
RUN mkdir -p /app
WORKDIR /app
COPY data /app/data
COPY run.sh propagate.py /app/
RUN printf '{"results":[]}\n' > /app/output.json
