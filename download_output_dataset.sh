#! /bin/sh
#
# upload_output_dataset.sh
# Copyright (C) 2025 TU Dresden
#
# Distributed under terms of the MIT license.
#

rsync --exclude .gitignore --partial --progress -avz male646f@dgw.zih.tu-dresden.de:/glw/netdresdat/private-dns-constrained-eval-mlenders/ output_dataset/
