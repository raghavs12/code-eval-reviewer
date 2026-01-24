FROM public.ecr.aws/x8v8d7g8/mars-base:latest

WORKDIR /app

COPY . .

RUN uv sync --dev

CMD ["/bin/bash"]
