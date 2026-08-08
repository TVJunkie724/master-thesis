# syntax=docker/dockerfile:1.7@sha256:a57df69d0ea827fb7266491f2813635de6f17269be881f696fbfdf2d83dda33e

FROM public.ecr.aws/lambda/python:3.11@sha256:224c112c0a36afa89f44e575d4f7bbd263cf312055672a46461271dee3c822e1

COPY requirements.txt constraints.txt /tmp/
RUN pip install --no-cache-dir --upgrade \
    --target "${LAMBDA_TASK_ROOT}" \
    -r /tmp/requirements.txt \
    -c /tmp/constraints.txt
COPY phase8_eventing "${LAMBDA_TASK_ROOT}/phase8_eventing"

CMD ["phase8_eventing.aws.runtime.lambda_handler"]
