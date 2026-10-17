FROM mcr.microsoft.com/devcontainers/python:1-3.11-bookworm

# Purge the broken Yarn repository before any DevContainer features run apt-get update
RUN rm -f /etc/apt/sources.list.d/yarn.list
