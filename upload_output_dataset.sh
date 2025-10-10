#! /bin/sh
#
# upload_output_dataset.sh
# Copyright (C) 2025 TU Dresden
#
# Distributed under terms of the MIT license.
#

rsync --exclude coap-* --exclude oscore-* --exclude lost+found/ --exclude *.coap.csv --exclude *.eth.csv --exclude *.merged.csv --exclude .gitignore --exclude .ipynb_checkpoints/ --exclude docker-compose-*.log --exclude *.stderr.log --exclude *server.log --partial --progress -avz output_dataset/ male646f@dgw.zih.tu-dresden.de:/glw/netdresdat/private-dns-constrained-eval-mlenders/
