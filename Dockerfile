FROM lambci/lambda:build-python3.6

RUN pip install --upgrade pip
RUN pip install lxml