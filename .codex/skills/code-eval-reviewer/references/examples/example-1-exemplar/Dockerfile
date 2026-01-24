FROM public.ecr.aws/x8v8d7g8/mars-base:latest

WORKDIR /app
COPY . .

# Install project dependencies 
RUN python -m pip install -e . && \
    python -m pip install -r requirements-tests.txt;

CMD ["/bin/bash"]
