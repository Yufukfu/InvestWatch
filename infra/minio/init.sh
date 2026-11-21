#!/bin/sh
# One-shot (service minio-init): creates the private bucket and the app user that services use.
# Idempotent: safe on every `docker compose up`; existing objects are never touched.
# The root credentials stay in this container and in minio; services only get MINIO_ACCESS_KEY/SECRET_KEY.
set -eu
: "${MINIO_ROOT_USER:?}" "${MINIO_ROOT_PASSWORD:?}" "${MINIO_ACCESS_KEY:?}" "${MINIO_SECRET_KEY:?}" "${MINIO_BUCKET:?}"
export MC_CONFIG_DIR=/tmp/mc
# Credentials through the environment, not argv (argv is visible in the process list).
export MC_HOST_iw="http://${MINIO_ROOT_USER}:${MINIO_ROOT_PASSWORD}@minio:9000"

mc ready iw >/dev/null
mc mb --ignore-existing "iw/${MINIO_BUCKET}"
mc anonymous set none "iw/${MINIO_BUCKET}" >/dev/null

policy=/tmp/iw-bucket-rw.json
cat >"$policy" <<EOF
{
  "Version": "2012-10-17",
  "Statement": [
    { "Effect": "Allow", "Action": ["s3:ListBucket", "s3:GetBucketLocation"], "Resource": ["arn:aws:s3:::${MINIO_BUCKET}"] },
    { "Effect": "Allow", "Action": ["s3:GetObject", "s3:PutObject", "s3:DeleteObject"], "Resource": ["arn:aws:s3:::${MINIO_BUCKET}/*"] }
  ]
}
EOF
mc admin policy create iw iw-bucket-rw "$policy" >/dev/null
# `user add` on an existing user updates its secret, so a rotated MINIO_SECRET_KEY takes effect.
printf '%s\n%s\n' "$MINIO_ACCESS_KEY" "$MINIO_SECRET_KEY" | mc admin user add iw >/dev/null
# The image has no grep: match the user's policies with a shell pattern.
case $(mc admin user info iw "$MINIO_ACCESS_KEY") in
  *iw-bucket-rw*) ;;
  *) mc admin policy attach iw iw-bucket-rw --user "$MINIO_ACCESS_KEY" >/dev/null ;;
esac
echo "minio-init: bucket ${MINIO_BUCKET} ready, app user ${MINIO_ACCESS_KEY} limited to it"
