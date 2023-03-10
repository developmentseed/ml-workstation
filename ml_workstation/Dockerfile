#FROM pangeo/pytorch-notebook
FROM pangeo/base-notebook

ARG SSH_PUBLIC_KEY

RUN mkdir -p .ssh
RUN echo ${SSH_PUBLIC_KEY} > .ssh/authorized_keys

RUN chmod 400 .ssh/authorized_keys
