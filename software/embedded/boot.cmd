# Full initial configuration happens once in U-Boot, before Linux drivers probe.
# Runtime algorithm changes must use the Linux driver and partial images.
if fatload mmc 0:1 0x10000000 system.bit; then
    if fpga loadb 0 0x10000000 ${filesize}; then
        if fatload mmc 0:1 0x03000000 system.dtb; then
            if fatload mmc 0:1 0x02000000 zImage; then
                setenv bootargs 'console=ttyPS0,115200 root=/dev/mmcblk0p2 rw rootwait cma=32M'
                bootz 0x02000000 - 0x03000000
            fi
        fi
    fi
fi
echo 'Hash accelerator boot failed; Linux was not started.'
