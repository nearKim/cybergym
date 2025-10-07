# syntax=docker/dockerfile:1

FROM ubuntu:22.04
RUN apt-get update && apt-get install -y ca-certificates curl gnupg
