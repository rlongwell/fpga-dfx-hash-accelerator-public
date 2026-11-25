/* SPDX-License-Identifier: MIT */
#ifndef HASH_ACCEL_UAPI_H
#define HASH_ACCEL_UAPI_H
#include <linux/ioctl.h>
#include <linux/types.h>

struct hash_info { __u32 abi, algorithm, buffer_size, status; };
struct hash_result { __u8 digest[32]; __u64 cycles; __u32 status, error; };
struct hash_switch { __u32 algorithm; char firmware[128]; __u32 reserved; __u64 manager_load_ns; };
#define HASH_INFO     _IOR('H', 0, struct hash_info)
#define HASH_START    _IOW('H', 1, __u64)
#define HASH_TRANSFER _IOW('H', 2, __u32)
#define HASH_RESULT   _IOR('H', 3, struct hash_result)
#define HASH_SWITCH   _IOWR('H', 4, struct hash_switch)
#define HASH_ABORT    _IO('H', 5)
#endif
