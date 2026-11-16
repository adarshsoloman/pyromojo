# audioop v0.1.0 benchmark report

- Generated: 2026-11-16T09:54:02
- CPU: AMD Ryzen 7 6800H with Radeon Graphics (16 cores)
- OS: Linux-7.0.0-28-generic-x86_64-with-glibc2.39
- Python: 3.13.14 (host); CPython Python 3.12.3 (reference)
- Mojo: Mojo 1.2.0 (2016d0cd)
- Git: 8b7596d; seed 20260610
- Cold compile: bench.mojo 2.06s, CLI 1.84s
- Runs: 2; 25 measured samples per cell per run (5 warmup discarded); headline numbers are medians-of-medians

Paths: `pure` = pure-Python floor (same semantics, no C); `c` = CPython 3.12.3 C audioop, timed in-process; `mojo` = native kernel measured in-process inside bench.mojo (fresh process per workload, 64-bit IEEE-754 double work included where the reference uses it); `cli` = full CLI request path (process spawn + framing + kernel), measured separately and never conflated with kernel numbers.

Correctness: every benchmarked cell passed a three-way gate (pure Python == CPython C == Mojo, exact bytes/state). NaN-factor inputs are excluded from benchmarking per the frozen Phase 0 policy (documented Mojo NaN->0 behaviour, no compatibility claim); infinities are included where defined.

## 1. Operation results (median ns, median-of-medians)

| op | workload | width | frames | bytes | pure | c | mojo | mojo/pure | mojo/c | gate |
|---|---|---|---:|---:|---:|---:|---:|---:|---:|---|
| add |  | 1 | 160 | 160 | 45696 | 346 | 1157 | 39.50 | 0.30 | PASS |
| bias |  | 1 | 160 | 160 | 35677 | 296 | 751 | 47.47 | 0.39 | PASS |
| mul |  | 1 | 160 | 160 | 46362 | 621 | 816 | 56.78 | 0.76 | PASS |
| byteswap |  | 1 | 160 | 160 | 21240 | 306 | 395 | 53.70 | 0.77 | PASS |
| reverse |  | 1 | 160 | 160 | 28874 | 315 | 416 | 69.41 | 0.76 | PASS |
| add |  | 1 | 4096 | 4096 | 1278651 | 7358 | 25097 | 50.95 | 0.29 | PASS |
| bias |  | 1 | 4096 | 4096 | 952136 | 4078 | 16897 | 56.35 | 0.24 | PASS |
| mul |  | 1 | 4096 | 4096 | 1253625 | 10454 | 17568 | 71.36 | 0.60 | PASS |
| byteswap |  | 1 | 4096 | 4096 | 634126 | 4063 | 9032 | 70.21 | 0.45 | PASS |
| reverse |  | 1 | 4096 | 4096 | 772847 | 4082 | 9503 | 81.33 | 0.43 | PASS |
| add |  | 1 | 65536 | 65536 | 20518990 | 56682 | 451967 | 45.40 | 0.13 | PASS |
| bias |  | 1 | 65536 | 65536 | 15097338 | 62197 | 282533 | 53.44 | 0.22 | PASS |
| mul |  | 1 | 65536 | 65536 | 20183422 | 101335 | 286606 | 70.42 | 0.35 | PASS |
| byteswap |  | 1 | 65536 | 65536 | 10262173 | 47369 | 140114 | 73.24 | 0.34 | PASS |
| reverse |  | 1 | 65536 | 65536 | 12508550 | 47830 | 143866 | 86.95 | 0.33 | PASS |
| add |  | 2 | 160 | 320 | 52589 | 306 | 1513 | 34.76 | 0.20 | PASS |
| bias |  | 2 | 160 | 320 | 41643 | 245 | 1117 | 37.28 | 0.22 | PASS |
| mul |  | 2 | 160 | 320 | 65478 | 586 | 1142 | 57.31 | 0.51 | PASS |
| byteswap |  | 2 | 160 | 320 | 34735 | 415 | 737 | 47.13 | 0.56 | PASS |
| reverse |  | 2 | 160 | 320 | 22557 | 391 | 821 | 27.46 | 0.48 | PASS |
| add |  | 2 | 4096 | 8192 | 1420043 | 5951 | 35772 | 39.70 | 0.17 | PASS |
| bias |  | 2 | 4096 | 8192 | 1079446 | 2139 | 28719 | 37.59 | 0.07 | PASS |
| mul |  | 2 | 4096 | 8192 | 1316353 | 11822 | 24526 | 53.67 | 0.48 | PASS |
| byteswap |  | 2 | 4096 | 8192 | 672879 | 4553 | 17713 | 37.99 | 0.26 | PASS |
| reverse |  | 2 | 4096 | 8192 | 817211 | 6352 | 17994 | 45.42 | 0.35 | PASS |
| add |  | 2 | 65536 | 131072 | 22474398 | 47439 | 646675 | 34.75 | 0.07 | PASS |
| bias |  | 2 | 65536 | 131072 | 17893803 | 15870 | 422096 | 42.39 | 0.04 | PASS |
| mul |  | 2 | 65536 | 131072 | 21529867 | 115789 | 392626 | 54.84 | 0.29 | PASS |
| byteswap |  | 2 | 65536 | 131072 | 11195663 | 44013 | 289751 | 38.64 | 0.15 | PASS |
| reverse |  | 2 | 65536 | 131072 | 13235671 | 44098 | 317368 | 41.70 | 0.14 | PASS |
| add |  | 4 | 160 | 640 | 57704 | 381 | 2330 | 24.77 | 0.16 | PASS |
| bias |  | 4 | 160 | 640 | 54232 | 270 | 1829 | 29.65 | 0.15 | PASS |
| mul |  | 4 | 160 | 640 | 59066 | 842 | 2084 | 28.34 | 0.40 | PASS |
| byteswap |  | 4 | 160 | 640 | 25814 | 606 | 1407 | 18.34 | 0.43 | PASS |
| reverse |  | 4 | 160 | 640 | 24917 | 521 | 1502 | 16.58 | 0.35 | PASS |
| add |  | 4 | 4096 | 16384 | 1511461 | 9718 | 66460 | 22.74 | 0.15 | PASS |
| bias |  | 4 | 4096 | 16384 | 1367739 | 4183 | 44529 | 30.72 | 0.09 | PASS |
| mul |  | 4 | 4096 | 16384 | 1522221 | 12133 | 39545 | 38.49 | 0.31 | PASS |
| byteswap |  | 4 | 4096 | 16384 | 687652 | 7639 | 35502 | 19.37 | 0.22 | PASS |
| reverse |  | 4 | 4096 | 16384 | 816259 | 5696 | 37766 | 21.61 | 0.15 | PASS |
| add |  | 4 | 65536 | 262144 | 23922695 | 369096 | 1081620 | 22.12 | 0.34 | PASS |
| bias |  | 4 | 65536 | 262144 | 22019605 | 29175 | 724506 | 30.39 | 0.04 | PASS |
| mul |  | 4 | 65536 | 262144 | 24522612 | 116986 | 722177 | 33.96 | 0.16 | PASS |
| byteswap |  | 4 | 65536 | 262144 | 11031964 | 73734 | 564995 | 19.53 | 0.13 | PASS |
| reverse |  | 4 | 65536 | 262144 | 13354044 | 57719 | 575595 | 23.20 | 0.10 | PASS |
| add |  | 2 | 160 | 640 | 104852 | 1082 | 3256 | 32.20 | 0.33 | PASS |
| tomono |  | 2 | 160 | 640 | 74976 | 1017 | 1989 | 37.70 | 0.51 | PASS |
| tomono |  | 2 | 4096 | 16384 | 1952868 | 15865 | 47990 | 40.69 | 0.33 | PASS |
| tomono |  | 2 | 65536 | 262144 | 31549651 | 152868 | 693268 | 45.51 | 0.22 | PASS |
| tostereo |  | 2 | 160 | 320 | 76148 | 1287 | 1768 | 43.07 | 0.73 | PASS |
| tostereo |  | 2 | 4096 | 8192 | 1996100 | 21761 | 38948 | 51.25 | 0.56 | PASS |
| tostereo |  | 2 | 65536 | 131072 | 32499027 | 212080 | 630665 | 51.53 | 0.34 | PASS |
| max |  | 1 | 160 | 160 | 25808 | 140 | 416 | 62.04 | 0.34 | PASS |
| minmax |  | 1 | 160 | 160 | 24351 | 280 | 416 | 58.54 | 0.67 | PASS |
| avg |  | 1 | 160 | 160 | 18064 | 280 | 451 | 40.05 | 0.62 | PASS |
| rms |  | 1 | 160 | 160 | 20368 | 270 | 471 | 43.25 | 0.57 | PASS |
| cross |  | 1 | 160 | 160 | 19526 | 150 | 426 | 45.84 | 0.35 | PASS |
| avgpp |  | 1 | 160 | 160 | 41177 | 336 | 701 | 58.74 | 0.48 | PASS |
| maxpp |  | 1 | 160 | 160 | 38728 | 316 | 636 | 60.89 | 0.50 | PASS |
| max |  | 1 | 4096 | 4096 | 521534 | 3166 | 9929 | 52.53 | 0.32 | PASS |
| minmax |  | 1 | 4096 | 4096 | 503485 | 2930 | 9212 | 54.66 | 0.32 | PASS |
| avg |  | 1 | 4096 | 4096 | 516454 | 4579 | 10069 | 51.29 | 0.45 | PASS |
| rms |  | 1 | 4096 | 4096 | 569158 | 3186 | 11346 | 50.16 | 0.28 | PASS |
| cross |  | 1 | 4096 | 4096 | 583024 | 2890 | 9247 | 63.05 | 0.31 | PASS |
| avgpp |  | 1 | 4096 | 4096 | 1136894 | 4152 | 15860 | 71.68 | 0.26 | PASS |
| maxpp |  | 1 | 4096 | 4096 | 1053246 | 5941 | 14657 | 71.86 | 0.41 | PASS |
| max |  | 1 | 65536 | 65536 | 8660145 | 44053 | 150719 | 57.46 | 0.29 | PASS |
| minmax |  | 1 | 65536 | 65536 | 8102038 | 29586 | 160278 | 50.55 | 0.18 | PASS |
| avg |  | 1 | 65536 | 65536 | 8471048 | 44032 | 167130 | 50.69 | 0.26 | PASS |
| rms |  | 1 | 65536 | 65536 | 9187595 | 46542 | 185755 | 49.46 | 0.25 | PASS |
| cross |  | 1 | 65536 | 65536 | 9513931 | 43727 | 158314 | 60.10 | 0.28 | PASS |
| avgpp |  | 1 | 65536 | 65536 | 18330622 | 65603 | 255732 | 71.68 | 0.26 | PASS |
| maxpp |  | 1 | 65536 | 65536 | 16848847 | 57323 | 243659 | 69.15 | 0.24 | PASS |
| max |  | 2 | 160 | 320 | 33137 | 185 | 571 | 58.03 | 0.32 | PASS |
| minmax |  | 2 | 160 | 320 | 20103 | 396 | 576 | 34.90 | 0.69 | PASS |
| avg |  | 2 | 160 | 320 | 20659 | 360 | 686 | 30.12 | 0.53 | PASS |
| rms |  | 2 | 160 | 320 | 22753 | 366 | 646 | 35.22 | 0.57 | PASS |
| cross |  | 2 | 160 | 320 | 21390 | 331 | 666 | 32.12 | 0.50 | PASS |
| avgpp |  | 2 | 160 | 320 | 45215 | 461 | 761 | 59.42 | 0.61 | PASS |
| maxpp |  | 2 | 160 | 320 | 42320 | 481 | 877 | 48.26 | 0.55 | PASS |
| max |  | 2 | 4096 | 8192 | 572975 | 9543 | 15238 | 37.60 | 0.63 | PASS |
| minmax |  | 2 | 4096 | 8192 | 527545 | 5400 | 15233 | 34.63 | 0.35 | PASS |
| avg |  | 2 | 4096 | 8192 | 552372 | 6417 | 12178 | 45.36 | 0.53 | PASS |
| rms |  | 2 | 4096 | 8192 | 608001 | 4794 | 13044 | 46.61 | 0.37 | PASS |
| cross |  | 2 | 4096 | 8192 | 598363 | 4844 | 15283 | 39.15 | 0.32 | PASS |
| avgpp |  | 2 | 4096 | 8192 | 1151647 | 8566 | 21796 | 52.84 | 0.39 | PASS |
| maxpp |  | 2 | 4096 | 8192 | 1082517 | 7829 | 16676 | 64.91 | 0.47 | PASS |
| max |  | 2 | 65536 | 131072 | 9165649 | 181006 | 213658 | 42.90 | 0.85 | PASS |
| minmax |  | 2 | 65536 | 131072 | 8686114 | 37065 | 214970 | 40.41 | 0.17 | PASS |
| avg |  | 2 | 65536 | 131072 | 8929208 | 44639 | 195904 | 45.58 | 0.23 | PASS |
| rms |  | 2 | 65536 | 131072 | 9974344 | 44599 | 275339 | 36.23 | 0.16 | PASS |
| cross |  | 2 | 65536 | 131072 | 9700823 | 151781 | 250437 | 38.74 | 0.61 | PASS |
| avgpp |  | 2 | 65536 | 131072 | 18802396 | 180019 | 435571 | 43.17 | 0.41 | PASS |
| maxpp |  | 2 | 65536 | 131072 | 17487305 | 175220 | 309223 | 56.55 | 0.57 | PASS |
| max |  | 4 | 160 | 640 | 24451 | 151 | 901 | 27.12 | 0.17 | PASS |
| minmax |  | 4 | 160 | 640 | 22433 | 306 | 1087 | 20.64 | 0.28 | PASS |
| avg |  | 4 | 160 | 640 | 22933 | 381 | 931 | 24.62 | 0.41 | PASS |
| rms |  | 4 | 160 | 640 | 24696 | 411 | 791 | 31.22 | 0.52 | PASS |
| cross |  | 4 | 160 | 640 | 22371 | 306 | 1087 | 20.58 | 0.28 | PASS |
| avgpp |  | 4 | 160 | 640 | 49479 | 420 | 1162 | 42.56 | 0.36 | PASS |
| maxpp |  | 4 | 160 | 640 | 45761 | 451 | 1127 | 40.59 | 0.40 | PASS |
| max |  | 4 | 4096 | 16384 | 641274 | 4303 | 21571 | 29.73 | 0.20 | PASS |
| minmax |  | 4 | 4096 | 16384 | 576853 | 4378 | 25343 | 22.76 | 0.17 | PASS |
| avg |  | 4 | 4096 | 16384 | 592913 | 6347 | 27221 | 21.78 | 0.23 | PASS |
| rms |  | 4 | 4096 | 16384 | 649424 | 6392 | 23179 | 28.02 | 0.28 | PASS |
| cross |  | 4 | 4096 | 16384 | 575956 | 1918 | 21561 | 26.71 | 0.09 | PASS |
| avgpp |  | 4 | 4096 | 16384 | 1277179 | 5440 | 28739 | 44.44 | 0.19 | PASS |
| maxpp |  | 4 | 4096 | 16384 | 1149824 | 6116 | 43216 | 26.61 | 0.14 | PASS |
| max |  | 4 | 65536 | 262144 | 10484196 | 29396 | 350316 | 29.93 | 0.08 | PASS |
| minmax |  | 4 | 65536 | 262144 | 9128945 | 29456 | 344460 | 26.50 | 0.09 | PASS |
| avg |  | 4 | 65536 | 262144 | 9784441 | 44078 | 284402 | 34.40 | 0.15 | PASS |
| rms |  | 4 | 65536 | 262144 | 10704341 | 66010 | 298167 | 35.90 | 0.22 | PASS |
| cross |  | 4 | 65536 | 262144 | 9278642 | 29370 | 421084 | 22.04 | 0.07 | PASS |
| avgpp |  | 4 | 65536 | 262144 | 20473093 | 196120 | 662419 | 30.91 | 0.30 | PASS |
| maxpp |  | 4 | 65536 | 262144 | 18536805 | 173698 | 358526 | 51.70 | 0.48 | PASS |
| getsample | middle | 1 | 65536 | 65536 | 1162 | 85 | 30 | 38.73 | 2.83 | PASS |
| getsample | middle | 2 | 65536 | 131072 | 841 | 125 | 30 | 28.05 | 4.17 | PASS |
| getsample | middle | 4 | 65536 | 262144 | 536 | 80 | 30 | 17.87 | 2.67 | PASS |
| lin2lin |  | 2 | 160 | 320 | 58545 | 160 | 1513 | 38.69 | 0.11 | PASS |
| lin2lin |  | 2 | 160 | 320 | 35948 | 316 | 912 | 39.42 | 0.35 | PASS |
| lin2lin |  | 2 | 4096 | 8192 | 993568 | 4388 | 39509 | 25.15 | 0.11 | PASS |
| lin2lin |  | 2 | 4096 | 8192 | 967720 | 3251 | 23013 | 42.05 | 0.14 | PASS |
| lin2lin |  | 2 | 65536 | 131072 | 16089890 | 29571 | 584212 | 27.54 | 0.05 | PASS |
| lin2lin |  | 2 | 65536 | 131072 | 15516678 | 30112 | 332517 | 46.66 | 0.09 | PASS |
| lin2lin |  | 4 | 4096 | 16384 | 974864 | 6121 | 33668 | 28.95 | 0.18 | PASS |
| lin2alaw |  | 1 | 160 | 160 | 79210 | 757 | 1588 | 49.88 | 0.48 | PASS |
| lin2ulaw |  | 1 | 160 | 160 | 78673 | 866 | 1422 | 55.31 | 0.61 | PASS |
| lin2alaw |  | 1 | 4096 | 4096 | 2093694 | 13109 | 33788 | 61.96 | 0.39 | PASS |
| lin2ulaw |  | 1 | 4096 | 4096 | 2093749 | 19196 | 34716 | 60.31 | 0.55 | PASS |
| lin2alaw |  | 1 | 65536 | 65536 | 33424422 | 126183 | 613077 | 54.52 | 0.21 | PASS |
| lin2ulaw |  | 1 | 65536 | 65536 | 33644487 | 136708 | 578105 | 58.20 | 0.24 | PASS |
| lin2alaw |  | 2 | 160 | 320 | 114777 | 411 | 1468 | 78.19 | 0.28 | PASS |
| lin2ulaw |  | 2 | 160 | 320 | 116414 | 691 | 1593 | 73.06 | 0.43 | PASS |
| lin2alaw |  | 2 | 4096 | 8192 | 2162399 | 12654 | 44769 | 48.30 | 0.28 | PASS |
| lin2ulaw |  | 2 | 4096 | 8192 | 2173991 | 23214 | 43016 | 50.54 | 0.54 | PASS |
| lin2alaw |  | 2 | 65536 | 131072 | 34745078 | 461320 | 2516091 | 13.81 | 0.18 | PASS |
| lin2ulaw |  | 2 | 65536 | 131072 | 35117931 | 507421 | 760524 | 46.18 | 0.67 | PASS |
| lin2alaw |  | 4 | 160 | 640 | 83547 | 546 | 2209 | 37.81 | 0.25 | PASS |
| lin2ulaw |  | 4 | 160 | 640 | 82976 | 776 | 1833 | 45.26 | 0.42 | PASS |
| lin2alaw |  | 4 | 4096 | 16384 | 2168250 | 8726 | 152082 | 14.26 | 0.06 | PASS |
| lin2ulaw |  | 4 | 4096 | 16384 | 2179130 | 19842 | 58705 | 37.12 | 0.34 | PASS |
| lin2alaw |  | 4 | 65536 | 262144 | 35186916 | 211870 | 1010115 | 34.83 | 0.21 | PASS |
| lin2ulaw |  | 4 | 65536 | 262144 | 35534021 | 348031 | 898089 | 39.57 | 0.39 | PASS |
| alaw2lin |  | 2 | 160 | 320 | 45034 | 426 | 3146 | 14.31 | 0.14 | PASS |
| alaw2lin |  | 2 | 4096 | 8192 | 1139699 | 2640 | 57533 | 19.81 | 0.05 | PASS |
| alaw2lin |  | 2 | 65536 | 131072 | 18475744 | 40867 | 942398 | 19.61 | 0.04 | PASS |
| ulaw2lin |  | 2 | 160 | 320 | 45616 | 260 | 2329 | 19.58 | 0.11 | PASS |
| ulaw2lin |  | 2 | 4096 | 8192 | 1136193 | 4278 | 57012 | 19.93 | 0.08 | PASS |
| ulaw2lin |  | 2 | 65536 | 131072 | 18264255 | 40807 | 943134 | 19.37 | 0.04 | PASS |
| alaw2lin |  | 2 | 160 | 160 | 34179 | 130 | 1553 | 22.00 | 0.08 | PASS |
| ulaw2lin |  | 2 | 160 | 160 | 22788 | 135 | 1252 | 18.19 | 0.11 | PASS |
| alaw2lin |  | 2 | 4096 | 4096 | 570065 | 2204 | 29085 | 19.60 | 0.08 | PASS |
| ulaw2lin |  | 2 | 4096 | 4096 | 567751 | 2214 | 40576 | 13.99 | 0.05 | PASS |
| alaw2lin |  | 2 | 65536 | 65536 | 9150174 | 33133 | 470011 | 19.47 | 0.07 | PASS |
| ulaw2lin |  | 2 | 65536 | 65536 | 8991395 | 20538 | 466901 | 19.26 | 0.04 | PASS |
| lin2adpcm | cold | 2 | 160 | 320 | 80517 | 631 | 1818 | 44.28 | 0.35 | PASS |
| adpcm2lin | cold | 2 | 160 | 80 | 64411 | 546 | 1723 | 37.37 | 0.32 | PASS |
| lin2adpcm | cold | 2 | 4096 | 8192 | 2097641 | 16551 | 42430 | 49.44 | 0.39 | PASS |
| adpcm2lin | cold | 2 | 4096 | 2048 | 1750637 | 10705 | 40115 | 43.64 | 0.27 | PASS |
| lin2adpcm | cold | 2 | 65536 | 131072 | 33617901 | 761912 | 714758 | 47.03 | 1.07 | PASS |
| adpcm2lin | cold | 2 | 65536 | 32768 | 27783581 | 168177 | 668987 | 41.53 | 0.25 | PASS |
| lin2adpcm | warm | 2 | 4096 | 8192 | 2098278 | 16461 | 45385 | 46.23 | 0.36 | PASS |
| adpcm2lin | warm | 2 | 4096 | 2048 | 1733299 | 10685 | 39048 | 44.39 | 0.27 | PASS |
| ratecv | cold 8k->16k | 2 | 160 | 320 | 180886 | 3176 | 4027 | 44.91 | 0.79 | PASS |
| ratecv | warm 8k->16k | 2 | 4096 | 8192 | 4734595 | 61050 | 93431 | 50.67 | 0.65 | PASS |
| ratecv | cold 44100->48000 | 2 | 4096 | 8192 | 3514749 | 45380 | 70087 | 50.15 | 0.65 | PASS |
| ratecv | stereo cold 8k->16k | 2 | 4096 | 16384 | 8356827 | 53391 | 174810 | 47.81 | 0.31 | PASS |
| ratecv | cold 8k->16k | 2 | 4096 | 8192 | 4709693 | 43672 | 90505 | 52.04 | 0.48 | PASS |
| ratecv | warm 8k->16k | 2 | 4096 | 8192 | 4766416 | 43687 | 93176 | 51.15 | 0.47 | PASS |
| ratecv | cold 44100->48000 | 2 | 4096 | 8192 | 3504294 | 38432 | 73814 | 47.47 | 0.52 | PASS |
| ratecv | stereo cold 8k->16k | 2 | 4096 | 16384 | 8277443 | 43336 | 176102 | 47.00 | 0.25 | PASS |
| ratecv | cold 8k->16k | 2 | 65536 | 131072 | 75643320 | 679592 | 1480973 | 51.08 | 0.46 | PASS |
| ratecv | warm 8k->16k | 2 | 4096 | 8192 | 4676105 | 43417 | 92018 | 50.82 | 0.47 | PASS |
| ratecv | cold 44100->48000 | 2 | 4096 | 8192 | 3488575 | 38257 | 70027 | 49.82 | 0.55 | PASS |
| ratecv | stereo cold 8k->16k | 2 | 4096 | 16384 | 8194331 | 42780 | 174253 | 47.03 | 0.25 | PASS |
| ratecv | cold 8k->16k | 1 | 4096 | 4096 | 4548449 | 40877 | 78473 | 57.96 | 0.52 | PASS |
| findmax | w1 | 2 | 4 | 8 | 3251 | 75 | 105 | 30.82 | 0.71 | PASS |
| findfit | w1 | 2 | 4 | 8 | 8095 | 190 | 135 | 59.96 | 1.41 | PASS |
| findfactor | w1 | 2 | 1 | 2 | 2058 | 145 | 110 | 18.71 | 1.32 | PASS |
| findmax | w8 | 2 | 32 | 64 | 19281 | 110 | 311 | 62.00 | 0.35 | PASS |
| findfit | w8 | 2 | 32 | 64 | 73143 | 686 | 496 | 147.47 | 1.38 | PASS |
| findfactor | w8 | 2 | 8 | 16 | 5010 | 211 | 165 | 30.36 | 1.28 | PASS |
| findmax | w64 | 2 | 256 | 512 | 80642 | 832 | 1703 | 47.35 | 0.49 | PASS |
| findfit | w64 | 2 | 256 | 512 | 3723929 | 22968 | 12839 | 290.05 | 1.79 | PASS |
| findfactor | w64 | 2 | 64 | 128 | 36288 | 180 | 581 | 62.46 | 0.31 | PASS |
| findmax | w8-large | 2 | 4096 | 8192 | 1472347 | 10625 | 18790 | 78.36 | 0.57 | PASS |
| add | content-silence | 2 | 4096 | 8192 | 1213549 | 6893 | 40481 | 29.98 | 0.17 | PASS |
| mul | content-silence | 2 | 4096 | 8192 | 1240961 | 16426 | 29516 | 42.04 | 0.56 | PASS |
| max | content-silence | 2 | 4096 | 8192 | 521273 | 4238 | 15459 | 33.72 | 0.27 | PASS |
| rms | content-silence | 2 | 4096 | 8192 | 588625 | 2870 | 13194 | 44.61 | 0.22 | PASS |
| cross | content-silence | 2 | 4096 | 8192 | 527615 | 4022 | 11321 | 46.60 | 0.36 | PASS |
| lin2ulaw | content-silence | 2 | 4096 | 8192 | 1512042 | 6277 | 18905 | 79.98 | 0.33 | PASS |
| lin2adpcm | content-silence | 2 | 4096 | 8192 | 1550239 | 18670 | 60393 | 25.67 | 0.31 | PASS |
| ratecv | cold content-silence | 2 | 4096 | 8192 | 2955429 | 80251 | 83206 | 35.52 | 0.96 | PASS |
| add | content-square | 2 | 4096 | 8192 | 1335574 | 5004 | 45065 | 29.64 | 0.11 | PASS |
| mul | content-square | 2 | 4096 | 8192 | 1296410 | 15464 | 26961 | 48.08 | 0.57 | PASS |
| max | content-square | 2 | 4096 | 8192 | 544041 | 4499 | 13370 | 40.69 | 0.34 | PASS |
| rms | content-square | 2 | 4096 | 8192 | 595939 | 4919 | 13230 | 45.04 | 0.37 | PASS |
| cross | content-square | 2 | 4096 | 8192 | 578165 | 3727 | 11637 | 49.68 | 0.32 | PASS |
| lin2ulaw | content-square | 2 | 4096 | 8192 | 1993976 | 11437 | 38533 | 51.75 | 0.30 | PASS |
| lin2adpcm | content-square | 2 | 4096 | 8192 | 2106067 | 45465 | 39524 | 53.29 | 1.15 | PASS |
| ratecv | cold content-square | 2 | 4096 | 8192 | 3497978 | 38803 | 71499 | 48.92 | 0.54 | PASS |
| add | content-sine | 2 | 4096 | 8192 | 1288891 | 6247 | 40461 | 31.85 | 0.15 | PASS |
| mul | content-sine | 2 | 4096 | 8192 | 1257732 | 16416 | 33588 | 37.45 | 0.49 | PASS |
| max | content-sine | 2 | 4096 | 8192 | 531452 | 6672 | 11321 | 46.94 | 0.59 | PASS |
| rms | content-sine | 2 | 4096 | 8192 | 582854 | 4874 | 13079 | 44.56 | 0.37 | PASS |
| cross | content-sine | 2 | 4096 | 8192 | 528366 | 4628 | 15419 | 34.27 | 0.30 | PASS |
| lin2ulaw | content-sine | 2 | 4096 | 8192 | 1585621 | 9287 | 23194 | 68.36 | 0.40 | PASS |
| lin2adpcm | content-sine | 2 | 4096 | 8192 | 1714745 | 16631 | 41639 | 41.18 | 0.40 | PASS |
| ratecv | cold content-sine | 2 | 4096 | 8192 | 3121082 | 38758 | 70042 | 44.56 | 0.55 | PASS |
| add | content-random | 2 | 4096 | 8192 | 1374973 | 6151 | 40651 | 33.82 | 0.15 | PASS |
| mul | content-random | 2 | 4096 | 8192 | 1301735 | 15248 | 27251 | 47.77 | 0.56 | PASS |
| max | content-random | 2 | 4096 | 8192 | 568598 | 8451 | 13425 | 42.35 | 0.63 | PASS |
| rms | content-random | 2 | 4096 | 8192 | 603739 | 6572 | 13230 | 45.63 | 0.50 | PASS |
| cross | content-random | 2 | 4096 | 8192 | 592297 | 5164 | 15494 | 38.23 | 0.33 | PASS |
| lin2ulaw | content-random | 2 | 4096 | 8192 | 2162103 | 24501 | 43953 | 49.19 | 0.56 | PASS |
| lin2adpcm | content-random | 2 | 4096 | 8192 | 2055862 | 36774 | 42545 | 48.32 | 0.86 | PASS |
| ratecv | cold content-random | 2 | 4096 | 8192 | 3496229 | 37826 | 69817 | 50.08 | 0.54 | PASS |
| add | content-sparse | 2 | 4096 | 8192 | 1195820 | 6517 | 36073 | 33.15 | 0.18 | PASS |
| mul | content-sparse | 2 | 4096 | 8192 | 1220642 | 15674 | 27020 | 45.17 | 0.58 | PASS |
| max | content-sparse | 2 | 4096 | 8192 | 517345 | 3311 | 11406 | 45.36 | 0.29 | PASS |
| rms | content-sparse | 2 | 4096 | 8192 | 578366 | 5936 | 15209 | 38.03 | 0.39 | PASS |
| cross | content-sparse | 2 | 4096 | 8192 | 524740 | 4648 | 13370 | 39.25 | 0.35 | PASS |
| lin2ulaw | content-sparse | 2 | 4096 | 8192 | 1536623 | 6622 | 19246 | 79.84 | 0.34 | PASS |
| lin2adpcm | content-sparse | 2 | 4096 | 8192 | 1574625 | 15699 | 50665 | 31.08 | 0.31 | PASS |
| ratecv | cold content-sparse | 2 | 4096 | 8192 | 2948967 | 67628 | 71465 | 41.26 | 0.95 | PASS |
| add | content-ramp | 2 | 4096 | 8192 | 1328992 | 6983 | 45205 | 29.40 | 0.15 | PASS |
| mul | content-ramp | 2 | 4096 | 8192 | 1300768 | 16426 | 27116 | 47.97 | 0.61 | PASS |
| max | content-ramp | 2 | 4096 | 8192 | 554495 | 4613 | 13465 | 41.18 | 0.34 | PASS |
| rms | content-ramp | 2 | 4096 | 8192 | 586696 | 4513 | 15309 | 38.32 | 0.29 | PASS |
| cross | content-ramp | 2 | 4096 | 8192 | 518217 | 3041 | 13390 | 38.70 | 0.23 | PASS |
| lin2ulaw | content-ramp | 2 | 4096 | 8192 | 2115941 | 12854 | 38377 | 55.13 | 0.33 | PASS |
| lin2adpcm | content-ramp | 2 | 4096 | 8192 | 1743989 | 20723 | 41799 | 41.72 | 0.50 | PASS |
| ratecv | cold content-ramp | 2 | 4096 | 8192 | 3260710 | 61120 | 88311 | 36.92 | 0.69 | PASS |
| add | content-clipped | 2 | 4096 | 8192 | 1296084 | 7013 | 45160 | 28.70 | 0.16 | PASS |
| mul | content-clipped | 2 | 4096 | 8192 | 1280300 | 16451 | 29606 | 43.24 | 0.56 | PASS |
| max | content-clipped | 2 | 4096 | 8192 | 537413 | 4078 | 13425 | 40.03 | 0.30 | PASS |
| rms | content-clipped | 2 | 4096 | 8192 | 600137 | 4503 | 15198 | 39.49 | 0.30 | PASS |
| cross | content-clipped | 2 | 4096 | 8192 | 556805 | 3126 | 11467 | 48.56 | 0.27 | PASS |
| lin2ulaw | content-clipped | 2 | 4096 | 8192 | 1856632 | 11311 | 33218 | 55.89 | 0.34 | PASS |
| lin2adpcm | content-clipped | 2 | 4096 | 8192 | 2027664 | 18019 | 42285 | 47.95 | 0.43 | PASS |
| ratecv | cold content-clipped | 2 | 4096 | 8192 | 3486486 | 61691 | 72096 | 48.36 | 0.86 | PASS |
| add | content-impulses | 2 | 4096 | 8192 | 1228753 | 6963 | 35958 | 34.17 | 0.19 | PASS |
| mul | content-impulses | 2 | 4096 | 8192 | 1235796 | 16330 | 27056 | 45.68 | 0.60 | PASS |
| max | content-impulses | 2 | 4096 | 8192 | 518533 | 6582 | 13390 | 38.73 | 0.49 | PASS |
| rms | content-impulses | 2 | 4096 | 8192 | 587273 | 6402 | 13235 | 44.37 | 0.48 | PASS |
| cross | content-impulses | 2 | 4096 | 8192 | 525241 | 4228 | 11381 | 46.15 | 0.37 | PASS |
| lin2ulaw | content-impulses | 2 | 4096 | 8192 | 1556225 | 8927 | 21781 | 71.45 | 0.41 | PASS |
| lin2adpcm | content-impulses | 2 | 4096 | 8192 | 1599136 | 16000 | 39925 | 40.05 | 0.40 | PASS |
| ratecv | cold content-impulses | 2 | 4096 | 8192 | 3032995 | 57067 | 72056 | 42.09 | 0.79 | PASS |

## 2. Per-operation aggregates (geometric mean over cells)

Categories use an explicit +/-10% tolerance band around parity:
`mojo/baseline > 1.10` = Mojo faster, `< 0.90` = Mojo slower,
otherwise comparable. Geometric means prevent large cells from
dominating; the full per-cell table above remains authoritative.

| op | cells | mojo/pure (geo) | mojo/c (geo) | vs pure | vs C |
|---|---:|---:|---:|---|---|
| add | 18 | 32.5x | 0.18x | Mojo faster | Mojo slower |
| adpcm2lin | 4 | 41.6x | 0.28x | Mojo faster | Mojo slower |
| alaw2lin | 6 | 19.0x | 0.07x | Mojo faster | Mojo slower |
| avg | 9 | 36.7x | 0.35x | Mojo faster | Mojo slower |
| avgpp | 9 | 51.1x | 0.34x | Mojo faster | Mojo slower |
| bias | 9 | 39.5x | 0.12x | Mojo faster | Mojo slower |
| byteswap | 9 | 37.1x | 0.32x | Mojo faster | Mojo slower |
| cross | 17 | 38.9x | 0.28x | Mojo faster | Mojo slower |
| findfactor | 3 | 32.9x | 0.81x | Mojo faster | Mojo slower |
| findfit | 3 | 136.9x | 1.52x | Mojo faster | Mojo faster |
| findmax | 4 | 51.6x | 0.51x | Mojo faster | Mojo slower |
| getsample | 3 | 26.9x | 3.16x | Mojo faster | Mojo faster |
| lin2adpcm | 12 | 42.2x | 0.48x | Mojo faster | Mojo slower |
| lin2alaw | 9 | 38.0x | 0.23x | Mojo faster | Mojo slower |
| lin2lin | 7 | 34.7x | 0.13x | Mojo faster | Mojo slower |
| lin2ulaw | 17 | 56.1x | 0.41x | Mojo faster | Mojo slower |
| max | 17 | 41.6x | 0.33x | Mojo faster | Mojo slower |
| maxpp | 9 | 52.4x | 0.39x | Mojo faster | Mojo slower |
| minmax | 9 | 35.9x | 0.27x | Mojo faster | Mojo slower |
| mul | 17 | 47.1x | 0.47x | Mojo faster | Mojo slower |
| ratecv | 21 | 47.1x | 0.55x | Mojo faster | Mojo slower |
| reverse | 9 | 39.1x | 0.29x | Mojo faster | Mojo slower |
| rms | 17 | 40.5x | 0.34x | Mojo faster | Mojo slower |
| tomono | 3 | 41.2x | 0.33x | Mojo faster | Mojo slower |
| tostereo | 3 | 48.5x | 0.52x | Mojo faster | Mojo slower |
| ulaw2lin | 6 | 18.3x | 0.07x | Mojo faster | Mojo slower |

## 3. Content sweep (width 2, 4096 frames, mojo ns)

| op | silence | square | sine | random | sparse | ramp | clipped | impulses |
|---|---|---|---|---|---|---|---|---|
| add | 40481 | 45065 | 40461 | 40651 | 36073 | 45205 | 45160 | 35958 |
| mul | 29516 | 26961 | 33588 | 27251 | 27020 | 27116 | 29606 | 27056 |
| max | 15459 | 13370 | 11321 | 13425 | 11406 | 13465 | 13425 | 13390 |
| rms | 13194 | 13230 | 13079 | 13230 | 15209 | 15309 | 15198 | 13235 |
| cross | 11321 | 11637 | 15419 | 15494 | 13370 | 13390 | 11467 | 11381 |
| lin2ulaw | 18905 | 38533 | 23194 | 43953 | 19246 | 38377 | 33218 | 21781 |
| lin2adpcm | 60393 | 39524 | 41639 | 42545 | 50665 | 41799 | 42285 | 39925 |
| ratecv | 83206 | 71499 | 70042 | 69817 | 71465 | 88311 | 72096 | 72056 |

## 4. Size scaling (mojo ns; representative workloads)

| op | w | 160f | 4096f | 65536f |
|---|---|---:|---:|---:|
| add | 1 | 1157 | 25097 | 451967 |
| add | 4 | 2330 | 66460 | 1081620 |
| mul | 1 | 816 | 17568 | 286606 |
| mul | 2 | 1142 | 24526 | 392626 |
| mul | 4 | 2084 | 39545 | 722177 |
| max | 1 | 416 | 9929 | 150719 |
| max | 2 | 571 | 15238 | 213658 |
| max | 4 | 901 | 21571 | 350316 |
| rms | 1 | 471 | 11346 | 185755 |
| rms | 2 | 646 | 13044 | 275339 |
| rms | 4 | 791 | 23179 | 298167 |
| lin2ulaw | 1 | 1422 | 34716 | 578105 |
| lin2ulaw | 2 | 1593 | 43016 | 760524 |
| lin2ulaw | 4 | 1833 | 58705 | 898089 |
| tomono | 2 | 1989 | 47990 | 693268 |

## 5. CLI request path (median-of-medians ns; process + framing included)

- Ping (empty `0x01` frame, process round-trip floor, median of 2 runs): 15932795 ns
- A CLI cell is dominated by process spawn (~ping floor); the kernel itself is a few microseconds at most. CLI numbers must not be read as kernel performance. Kernel time for a CLI-measured cell may be approximated as `cli - ping`.

| op | workload | cli | ping | cli-ping (est. kernel+framing) |
|---|---|---:|---:|---:|
| add |  | 15952033 | 15932795 | 19238 |
| bias |  | 16029174 | 15932795 | 96379 |
| mul |  | 16118974 | 15932795 | 186179 |
| byteswap |  | 15957854 | 15932795 | 25059 |
| reverse |  | 16001752 | 15932795 | 68957 |
| add |  | 16019896 | 15932795 | 87101 |
| bias |  | 15886044 | 15932795 | 0 |
| mul |  | 16151490 | 15932795 | 218695 |
| byteswap |  | 16399242 | 15932795 | 466447 |
| reverse |  | 15608721 | 15932795 | 0 |
| add |  | 16078317 | 15932795 | 145522 |
| bias |  | 16215395 | 15932795 | 282600 |
| mul |  | 17184569 | 15932795 | 1251774 |
| byteswap |  | 16442388 | 15932795 | 509593 |
| reverse |  | 16592862 | 15932795 | 660067 |
| add |  | 16158303 | 15932795 | 225508 |
| bias |  | 15938237 | 15932795 | 5442 |
| mul |  | 15901969 | 15932795 | 0 |
| byteswap |  | 15647559 | 15932795 | 0 |
| reverse |  | 15687644 | 15932795 | 0 |
| add |  | 16007247 | 15932795 | 74452 |
| bias |  | 15737969 | 15932795 | 0 |
| mul |  | 16036818 | 15932795 | 104023 |
| byteswap |  | 15873936 | 15932795 | 0 |
| reverse |  | 15983523 | 15932795 | 50728 |
| add |  | 16937171 | 15932795 | 1004376 |
| bias |  | 16471593 | 15932795 | 538798 |
| mul |  | 17704158 | 15932795 | 1771363 |
| byteswap |  | 17060985 | 15932795 | 1128190 |
| reverse |  | 16774940 | 15932795 | 842145 |
| add |  | 16418583 | 15932795 | 485788 |
| bias |  | 16157361 | 15932795 | 224566 |
| mul |  | 15946287 | 15932795 | 13492 |
| byteswap |  | 16159980 | 15932795 | 227185 |
| reverse |  | 16077114 | 15932795 | 144319 |
| add |  | 15868330 | 15932795 | 0 |
| bias |  | 15943622 | 15932795 | 10827 |
| mul |  | 16208637 | 15932795 | 275842 |
| byteswap |  | 15998211 | 15932795 | 65416 |
| reverse |  | 15806899 | 15932795 | 0 |
| add |  | 16642635 | 15932795 | 709840 |
| bias |  | 16796646 | 15932795 | 863851 |
| mul |  | 17703872 | 15932795 | 1771077 |
| byteswap |  | 17630474 | 15932795 | 1697679 |
| reverse |  | 17744449 | 15932795 | 1811654 |
| add |  | 16152702 | 15932795 | 219907 |
| tomono |  | 15623989 | 15932795 | 0 |
| tomono |  | 16113207 | 15932795 | 180412 |
| tomono |  | 17995447 | 15932795 | 2062652 |
| tostereo |  | 16156268 | 15932795 | 223473 |
| tostereo |  | 16209860 | 15932795 | 277065 |
| tostereo |  | 17908633 | 15932795 | 1975838 |
| max |  | 16287731 | 15932795 | 354936 |
| minmax |  | 15874762 | 15932795 | 0 |
| avg |  | 16036056 | 15932795 | 103261 |
| rms |  | 16140363 | 15932795 | 207568 |
| cross |  | 16000218 | 15932795 | 67423 |
| avgpp |  | 15959242 | 15932795 | 26447 |
| maxpp |  | 16241449 | 15932795 | 308654 |
| max |  | 15787502 | 15932795 | 0 |
| minmax |  | 16033301 | 15932795 | 100506 |
| avg |  | 15728005 | 15932795 | 0 |
| rms |  | 16169157 | 15932795 | 236362 |
| cross |  | 15842531 | 15932795 | 0 |
| avgpp |  | 15817985 | 15932795 | 0 |
| maxpp |  | 16359712 | 15932795 | 426917 |
| max |  | 16196369 | 15932795 | 263574 |
| minmax |  | 16346206 | 15932795 | 413411 |
| avg |  | 16809761 | 15932795 | 876966 |
| rms |  | 16608802 | 15932795 | 676007 |
| cross |  | 16535809 | 15932795 | 603014 |
| avgpp |  | 16808904 | 15932795 | 876109 |
| maxpp |  | 16379183 | 15932795 | 446388 |
| max |  | 15920744 | 15932795 | 0 |
| minmax |  | 15996852 | 15932795 | 64057 |
| avg |  | 15678536 | 15932795 | 0 |
| rms |  | 16008193 | 15932795 | 75398 |
| cross |  | 16001632 | 15932795 | 68837 |
| avgpp |  | 16024504 | 15932795 | 91709 |
| maxpp |  | 15925448 | 15932795 | 0 |
| max |  | 15960744 | 15932795 | 27949 |
| minmax |  | 16499170 | 15932795 | 566375 |
| avg |  | 16179387 | 15932795 | 246592 |
| rms |  | 16265414 | 15932795 | 332619 |
| cross |  | 16155426 | 15932795 | 222631 |
| avgpp |  | 16082925 | 15932795 | 150130 |
| maxpp |  | 15890236 | 15932795 | 0 |
| max |  | 16352763 | 15932795 | 419968 |
| minmax |  | 16524167 | 15932795 | 591372 |
| avg |  | 16586334 | 15932795 | 653539 |
| rms |  | 16522192 | 15932795 | 589397 |
| cross |  | 16447527 | 15932795 | 514732 |
| avgpp |  | 16976149 | 15932795 | 1043354 |
| maxpp |  | 16615409 | 15932795 | 682614 |
| max |  | 15856011 | 15932795 | 0 |
| minmax |  | 15657973 | 15932795 | 0 |
| avg |  | 15541603 | 15932795 | 0 |
| rms |  | 15932245 | 15932795 | 0 |
| cross |  | 15724498 | 15932795 | 0 |
| avgpp |  | 15397777 | 15932795 | 0 |
| maxpp |  | 15774287 | 15932795 | 0 |
| max |  | 15904452 | 15932795 | 0 |
| minmax |  | 15929836 | 15932795 | 0 |
| avg |  | 15916295 | 15932795 | 0 |
| rms |  | 15903776 | 15932795 | 0 |
| cross |  | 15620642 | 15932795 | 0 |
| avgpp |  | 15369002 | 15932795 | 0 |
| maxpp |  | 15170949 | 15932795 | 0 |
| max |  | 16526280 | 15932795 | 593485 |
| minmax |  | 16303325 | 15932795 | 370530 |
| avg |  | 16448654 | 15932795 | 515859 |
| rms |  | 16264061 | 15932795 | 331266 |
| cross |  | 16349156 | 15932795 | 416361 |
| avgpp |  | 16719766 | 15932795 | 786971 |
| maxpp |  | 16494179 | 15932795 | 561384 |
| getsample | middle | 15606646 | 15932795 | 0 |
| getsample | middle | 15617070 | 15932795 | 0 |
| getsample | middle | 15767379 | 15932795 | 0 |
| lin2lin |  | 15573594 | 15932795 | 0 |
| lin2lin |  | 15309045 | 15932795 | 0 |
| lin2lin |  | 15459764 | 15932795 | 0 |
| lin2lin |  | 15451237 | 15932795 | 0 |
| lin2lin |  | 16864889 | 15932795 | 932094 |
| lin2lin |  | 16484131 | 15932795 | 551336 |
| lin2lin |  | 15191268 | 15932795 | 0 |
| lin2alaw |  | 15199843 | 15932795 | 0 |
| lin2ulaw |  | 15367961 | 15932795 | 0 |
| lin2alaw |  | 15242884 | 15932795 | 0 |
| lin2ulaw |  | 15295038 | 15932795 | 0 |
| lin2alaw |  | 16440178 | 15932795 | 507383 |
| lin2ulaw |  | 15930847 | 15932795 | 0 |
| lin2alaw |  | 15211275 | 15932795 | 0 |
| lin2ulaw |  | 15281382 | 15932795 | 0 |
| lin2alaw |  | 15263688 | 15932795 | 0 |
| lin2ulaw |  | 15256260 | 15932795 | 0 |
| lin2alaw |  | 16671244 | 15932795 | 738449 |
| lin2ulaw |  | 16875800 | 15932795 | 943005 |
| lin2alaw |  | 15231929 | 15932795 | 0 |
| lin2ulaw |  | 15227756 | 15932795 | 0 |
| lin2alaw |  | 15468390 | 15932795 | 0 |
| lin2ulaw |  | 15409859 | 15932795 | 0 |
| lin2alaw |  | 16892816 | 15932795 | 960021 |
| lin2ulaw |  | 16928654 | 15932795 | 995859 |
| alaw2lin |  | 15355527 | 15932795 | 0 |
| alaw2lin |  | 15513464 | 15932795 | 0 |
| alaw2lin |  | 17527027 | 15932795 | 1594232 |
| ulaw2lin |  | 15269505 | 15932795 | 0 |
| ulaw2lin |  | 15343619 | 15932795 | 0 |
| ulaw2lin |  | 17740906 | 15932795 | 1808111 |
| alaw2lin |  | 15243280 | 15932795 | 0 |
| ulaw2lin |  | 15356388 | 15932795 | 0 |
| alaw2lin |  | 15295854 | 15932795 | 0 |
| ulaw2lin |  | 15488097 | 15932795 | 0 |
| alaw2lin |  | 16730460 | 15932795 | 797665 |
| ulaw2lin |  | 16461472 | 15932795 | 528677 |
| lin2adpcm | cold | 15763536 | 15932795 | 0 |
| adpcm2lin | cold | 15326572 | 15932795 | 0 |
| lin2adpcm | cold | 15790156 | 15932795 | 0 |
| adpcm2lin | cold | 15700928 | 15932795 | 0 |
| lin2adpcm | cold | 16753283 | 15932795 | 820488 |
| adpcm2lin | cold | 16763627 | 15932795 | 830832 |
| lin2adpcm | warm | 15640579 | 15932795 | 0 |
| adpcm2lin | warm | 15421692 | 15932795 | 0 |
| ratecv | cold 8k->16k | 15384592 | 15932795 | 0 |
| ratecv | warm 8k->16k | 15728390 | 15932795 | 0 |
| ratecv | cold 44100->48000 | 15472182 | 15932795 | 0 |
| ratecv | stereo cold 8k->16k | 15764999 | 15932795 | 0 |
| ratecv | cold 8k->16k | 15637553 | 15932795 | 0 |
| ratecv | warm 8k->16k | 15618242 | 15932795 | 0 |
| ratecv | cold 44100->48000 | 15499077 | 15932795 | 0 |
| ratecv | stereo cold 8k->16k | 15633736 | 15932795 | 0 |
| ratecv | cold 8k->16k | 19393423 | 15932795 | 3460628 |
| ratecv | warm 8k->16k | 15592323 | 15932795 | 0 |
| ratecv | cold 44100->48000 | 15506757 | 15932795 | 0 |
| ratecv | stereo cold 8k->16k | 15649771 | 15932795 | 0 |
| ratecv | cold 8k->16k | 15574890 | 15932795 | 0 |
| findmax | w1 | 15153435 | 15932795 | 0 |
| findfit | w1 | 15275000 | 15932795 | 0 |
| findfactor | w1 | 15243751 | 15932795 | 0 |
| findmax | w8 | 15360496 | 15932795 | 0 |
| findfit | w8 | 15246701 | 15932795 | 0 |
| findfactor | w8 | 14918878 | 15932795 | 0 |
| findmax | w64 | 15323030 | 15932795 | 0 |
| findfit | w64 | 15135877 | 15932795 | 0 |
| findfactor | w64 | 15452494 | 15932795 | 0 |
| findmax | w8-large | 15494228 | 15932795 | 0 |
| add | content-silence | 15435267 | 15932795 | 0 |
| mul | content-silence | 15427497 | 15932795 | 0 |
| max | content-silence | 15312926 | 15932795 | 0 |
| rms | content-silence | 15266614 | 15932795 | 0 |
| cross | content-silence | 15432196 | 15932795 | 0 |
| lin2ulaw | content-silence | 15342772 | 15932795 | 0 |
| lin2adpcm | content-silence | 15219880 | 15932795 | 0 |
| ratecv | cold content-silence | 15645388 | 15932795 | 0 |
| add | content-square | 15213733 | 15932795 | 0 |
| mul | content-square | 15133232 | 15932795 | 0 |
| max | content-square | 15331932 | 15932795 | 0 |
| rms | content-square | 15453586 | 15932795 | 0 |
| cross | content-square | 16416031 | 15932795 | 483236 |
| lin2ulaw | content-square | 16106603 | 15932795 | 173808 |
| lin2adpcm | content-square | 15488521 | 15932795 | 0 |
| ratecv | cold content-square | 15690553 | 15932795 | 0 |
| add | content-sine | 15443627 | 15932795 | 0 |
| mul | content-sine | 15430548 | 15932795 | 0 |
| max | content-sine | 15459567 | 15932795 | 0 |
| rms | content-sine | 15348518 | 15932795 | 0 |
| cross | content-sine | 15177039 | 15932795 | 0 |
| lin2ulaw | content-sine | 15439464 | 15932795 | 0 |
| lin2adpcm | content-sine | 15402690 | 15932795 | 0 |
| ratecv | cold content-sine | 15509191 | 15932795 | 0 |
| add | content-random | 15327994 | 15932795 | 0 |
| mul | content-random | 15180832 | 15932795 | 0 |
| max | content-random | 15204171 | 15932795 | 0 |
| rms | content-random | 15111976 | 15932795 | 0 |
| cross | content-random | 15449889 | 15932795 | 0 |
| lin2ulaw | content-random | 15536037 | 15932795 | 0 |
| lin2adpcm | content-random | 15529969 | 15932795 | 0 |
| ratecv | cold content-random | 15612501 | 15932795 | 0 |
| add | content-sparse | 15484389 | 15932795 | 0 |
| mul | content-sparse | 15478688 | 15932795 | 0 |
| max | content-sparse | 15386895 | 15932795 | 0 |
| rms | content-sparse | 15369908 | 15932795 | 0 |
| cross | content-sparse | 15149237 | 15932795 | 0 |
| lin2ulaw | content-sparse | 15387291 | 15932795 | 0 |
| lin2adpcm | content-sparse | 15402084 | 15932795 | 0 |
| ratecv | cold content-sparse | 15529589 | 15932795 | 0 |
| add | content-ramp | 15358852 | 15932795 | 0 |
| mul | content-ramp | 15342246 | 15932795 | 0 |
| max | content-ramp | 15390492 | 15932795 | 0 |
| rms | content-ramp | 15473303 | 15932795 | 0 |
| cross | content-ramp | 15438107 | 15932795 | 0 |
| lin2ulaw | content-ramp | 15324793 | 15932795 | 0 |
| lin2adpcm | content-ramp | 15510423 | 15932795 | 0 |
| ratecv | cold content-ramp | 15930055 | 15932795 | 0 |
| add | content-clipped | 15381334 | 15932795 | 0 |
| mul | content-clipped | 15225255 | 15932795 | 0 |
| max | content-clipped | 15091197 | 15932795 | 0 |
| rms | content-clipped | 15018831 | 15932795 | 0 |
| cross | content-clipped | 15211549 | 15932795 | 0 |
| lin2ulaw | content-clipped | 15240128 | 15932795 | 0 |
| lin2adpcm | content-clipped | 15245799 | 15932795 | 0 |
| ratecv | cold content-clipped | 15342221 | 15932795 | 0 |
| add | content-impulses | 14971963 | 15932795 | 0 |
| mul | content-impulses | 15547788 | 15932795 | 0 |
| max | content-impulses | 15548399 | 15932795 | 0 |
| rms | content-impulses | 15391478 | 15932795 | 0 |
| cross | content-impulses | 15377226 | 15932795 | 0 |
| lin2ulaw | content-impulses | 15388593 | 15932795 | 0 |
| lin2adpcm | content-impulses | 15334796 | 15932795 | 0 |
| ratecv | cold content-impulses | 15496952 | 15932795 | 0 |

## 6. Cold start

- `mojo build bench.mojo`: 2.06 s (one-time; excluded from all medians)
- `mojo build cli.mojo`: 1.84 s (one-time; excluded from all medians)
- CLI process spawn floor (ping median): 15932795 ns
- In-process timing excludes process startup and dataset generation; input bytes are parsed once outside the timed loop (parsing is not part of any reported median).

## 7. Stability (per-cell max pairwise relative delta across runs)

- 125/250 cells within 5% across all runs; 62/250 within 20%; 63/250 noisy (>20%).
- The host is a shared 16-core desktop under load (IDE, browser). Benchmark subprocesses are pinned with taskset to the two least-loaded cores observed at start (11, 13 here), but no frequency locking was used, so residual run-to-run variance is environmental. Headline numbers use medians-of-medians; the ten noisiest cells follow.

| op | workload | run1 | run2 | max delta |
|---|---|---:|---:|---|
| lin2alaw |  | 48161 | 256003 | 431.6% |
| lin2alaw |  | 4202347 | 829835 | 406.4% |
| maxpp |  | 22593 | 63840 | 182.6% |
| minmax |  | 34095 | 16591 | 105.5% |
| lin2adpcm | content-silence | 40316 | 80471 | 99.6% |
| ulaw2lin |  | 51597 | 29556 | 74.6% |
| alaw2lin |  | 2335 | 3958 | 69.5% |
| alaw2lin |  | 1924 | 1183 | 62.6% |
| cross |  | 26531 | 16592 | 59.9% |
| findmax | w8 | 381 | 241 | 58.1% |

## 8. Bottleneck analysis

- Allocation: every native call allocates its result buffer (`List` grow) plus one decoded-`Int32` vector per fragment in `decode_fragment`. The kernel medians therefore include allocation; the C reference allocates a single output buffer. This is the dominant Mojo-vs-C gap on small inputs, where fixed overhead dominates.
- Int64 arithmetic: the port widens all samples to 64-bit and branches per element; the C inner loops work on native ints with pointer increments. No SIMD is used (Phase 10 is measurement-only).
- `ratecv`/`adpcm` carry per-call state vectors (`RatecvState`, two output lists); no persistent buffers are reused between calls.
- Content sensitivity: branchy peak-walk (`avgpp`/`maxpp`) and `findfit` inner loops vary with signal shape; `cross` on dense crossings is the cheapest statistic.

## 9. Limitations

- NaN-factor inputs are excluded from benchmarking per the frozen Phase 0 policy (Mojo defines NaN results as 0; the reference is undefined). Infinities are included where defined.
- `findmax` uses window 8 (plus one large window); `findfit` and `findfactor` use 8-sample windows scaled for the benchmark corpus, not the full Phase 2 differential ranges.
- CLI timings include process spawn (~ping floor) and are not comparable to in-process kernel numbers.
- Throughput cells assume the framed benchmark corpus; real-world audio with different content mixes will shift absolute numbers,
 but the per-op ordering is expected to hold.
