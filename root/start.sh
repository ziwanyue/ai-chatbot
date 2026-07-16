#!/bin/sh
# 转发 localhost:3306 -> host.docker.internal:3306
socat TCP-LISTEN:3306,fork,reuseaddr TCP:host.docker.internal:3306 &
sleep 2
cd /root/gewe/api
mkdir -p /var/run
exec ./xd java -jar finder-admin.jar
