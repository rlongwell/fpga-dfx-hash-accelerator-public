// SPDX-License-Identifier: GPL-2.0-only
// Original Linux DMAengine / FPGA-manager bridge for the static hash shell.
#include <linux/completion.h>
#include <linux/dmaengine.h>
#include <linux/dma-mapping.h>
#include <linux/fpga/fpga-mgr.h>
#include <linux/firmware.h>
#include <linux/fs.h>
#include <linux/io.h>
#include <linux/iopoll.h>
#include <linux/ktime.h>
#include <linux/miscdevice.h>
#include <linux/module.h>
#include <linux/mutex.h>
#include <linux/of.h>
#include <linux/platform_device.h>
#include <linux/uaccess.h>
#include <linux/version.h>
#include "hash_accel.h"

#define BUFFER_SIZE (1024 * 1024)
#define CONTROL 0x00
#define STATUS 0x04
#define ALGORITHM 0x08
#define VERSION 0x0c
#define LENGTH_LO 0x10
#define LENGTH_HI 0x14
#define DIGEST 0x20
#define CYCLES_LO 0x40
#define CYCLES_HI 0x44
#define ERROR_CODE 0x48
#define BUSY BIT(0)
#define DONE BIT(1)
#define ERROR BIT(2)
#define ISOLATED BIT(3)
#define READY BIT(4)

struct hash_device {
    struct device *dev, *dma_dev;
    struct miscdevice misc;
    void __iomem *regs;
    struct dma_chan *tx;
    struct fpga_manager *manager;
    void *buffer;
    dma_addr_t dma_address;
    struct completion completion;
    enum dmaengine_tx_result dma_result;
    struct mutex lock;
    atomic_t opened;
    u64 remaining;
    bool file_active, configuration_failed, dma_fault, dma_fault_pinned;
};

static int hash_stop(struct hash_device *h, bool retry_dma_fault)
{
    bool was_fault = h->dma_fault;
    bool keep_isolated;
    int ret;

    /* Only an explicit ABORT may retry and clear an existing DMA quarantine. */
    if (was_fault && !retry_dma_fault)
        return -EIO;
    ret = dmaengine_terminate_sync(h->tx);
    if (ret) {
        if (!h->dma_fault) {
            h->dma_fault = true;
            /* Keep callback code and the buffer owner resident after close. */
            h->dma_fault_pinned = try_module_get(THIS_MODULE);
        }
        writel(6, h->regs + CONTROL); /* Abort and isolate; DMA may still be active. */
        h->file_active = false;
        h->remaining = 0;
        dev_err(h->dev, "DMA termination failed (%d); isolated until ABORT recovery\n", ret);
        return ret;
    }

    /* A recovered DMA fault must not release a failed FPGA configuration. */
    keep_isolated = h->configuration_failed ||
                    (!was_fault && (readl(h->regs + STATUS) & ISOLATED));
    writel(2 | (keep_isolated ? 4 : 0), h->regs + CONTROL);
    h->file_active = false;
    h->remaining = 0;
    h->dma_fault = false;
    if (h->dma_fault_pinned) {
        h->dma_fault_pinned = false;
        module_put(THIS_MODULE);
    }
    return 0;
}

static void hash_dma_done(void *argument, const struct dmaengine_result *result)
{
    struct hash_device *h = argument;

    WRITE_ONCE(h->dma_result, result ? result->result : DMA_TRANS_ABORTED);
    complete(&h->completion);
}

static int hash_transfer(struct hash_device *h, u32 count)
{
    struct dma_async_tx_descriptor *descriptor;
    dma_cookie_t cookie;
    enum dma_status status;
    long wait;
    int ret;

    if (h->dma_fault)
        return -EIO;
    if (!h->file_active || !count || count > BUFFER_SIZE || count > h->remaining)
        return -EINVAL;
    reinit_completion(&h->completion);
    WRITE_ONCE(h->dma_result, DMA_TRANS_ABORTED);
    /* Coherent mappings still require ordering before making the DMA visible. */
    dma_wmb();
    descriptor = dmaengine_prep_slave_single(h->tx, h->dma_address, count,
                    DMA_MEM_TO_DEV, DMA_PREP_INTERRUPT | DMA_CTRL_ACK);
    if (!descriptor)
        return -EIO;
    descriptor->callback_result = hash_dma_done;
    descriptor->callback_param = h;
    cookie = dmaengine_submit(descriptor);
    if (dma_submit_error(cookie))
        return cookie;
    dma_async_issue_pending(h->tx);
    wait = wait_for_completion_interruptible_timeout(&h->completion, msecs_to_jiffies(10000));
    status = dma_async_is_tx_complete(h->tx, cookie, NULL, NULL);
    if (wait <= 0 || status != DMA_COMPLETE ||
        READ_ONCE(h->dma_result) != DMA_TRANS_NOERROR ||
        (readl(h->regs + STATUS) & ERROR)) {
        ret = hash_stop(h, false);
        if (ret)
            return ret;
        return wait < 0 ? wait : (wait == 0 ? -ETIMEDOUT : -EIO);
    }
    h->remaining -= count;
    return 0;
}

static int hash_switch_image(struct hash_device *h, struct hash_switch *request)
{
    struct fpga_image_info *image;
    const struct firmware *firmware;
    u32 status;
    int ret;
    u64 started;

    request->manager_load_ns = 0;
    request->reserved = 0;

    if (h->dma_fault)
        return -EIO;
    if (h->file_active || (readl(h->regs + STATUS) & BUSY))
        return -EBUSY;
    if (request->algorithm < 1 || request->algorithm > 3 ||
        !memchr(request->firmware, '\0', sizeof(request->firmware)) ||
        !request->firmware[0] || request->firmware[0] == '/' ||
        strstr(request->firmware, ".."))
        return -EINVAL;
    ret = hash_stop(h, false);
    if (ret)
        return ret;
    writel(4, h->regs + CONTROL);
    h->configuration_failed = true;
    ret = readl_poll_timeout(h->regs + STATUS, status, status & ISOLATED, 10, 100000);
    if (ret)
        return ret;
    image = fpga_image_info_alloc(h->dev);
    if (!image)
        return -ENOMEM;
    image->flags = FPGA_MGR_PARTIAL_RECONFIG;
    ret = fpga_mgr_lock(h->manager);
    if (!ret) {
#ifdef FPGA_MGR_CONFIG_DMA_BUF
        /* AMD's alternate DMA-BUF entry point precedes image->buf handling.
         * Refuse stale manager-global mode rather than load another image.
         */
        if (h->manager->flags & FPGA_MGR_CONFIG_DMA_BUF)
            ret = -EBUSY;
        else
#endif
        {
            started = ktime_get_ns();
            /* AMD 2024.2's firmware-name path replaces image->flags with
             * manager-global flags. Supplying the requested buffer preserves our
             * explicit partial flag and avoids resetting the static PL design.
             */
            ret = request_firmware(&firmware, request->firmware, h->dev);
            if (!ret) {
                image->buf = firmware->data;
                image->count = firmware->size;
                ret = fpga_mgr_load(h->manager, image);
                release_firmware(firmware);
            }
            request->manager_load_ns = ktime_get_ns() - started;
        }
        fpga_mgr_unlock(h->manager);
    }
    fpga_image_info_free(image);
    if (ret)
        return ret; /* Remain isolated on all configuration failures. */
    writel(8, h->regs + CONTROL); /* Clear sticky status and release isolation. */
    ret = readl_poll_timeout(h->regs + STATUS, status, status & READY, 10, 100000);
    if (!ret && readl(h->regs + ALGORITHM) != request->algorithm)
        ret = -EIO;
    if (ret)
        writel(4, h->regs + CONTROL);
    else
        h->configuration_failed = false;
    return ret;
}

static long hash_ioctl(struct file *file, unsigned int command, unsigned long argument)
{
    struct hash_device *h = file->private_data;
    void __user *user = (void __user *)argument;
    struct hash_info info;
    struct hash_result result = {0};
    struct hash_switch request;
    u64 length;
    u32 count, status, word;
    int ret = 0, stop_ret, i, j;

    if (mutex_lock_interruptible(&h->lock))
        return -ERESTARTSYS;
    switch (command) {
    case HASH_INFO:
        info.abi = readl(h->regs + VERSION);
        info.algorithm = readl(h->regs + ALGORITHM);
        info.buffer_size = BUFFER_SIZE;
        info.status = readl(h->regs + STATUS);
        ret = copy_to_user(user, &info, sizeof(info)) ? -EFAULT : 0;
        break;
    case HASH_START:
        if (copy_from_user(&length, user, sizeof(length))) { ret = -EFAULT; break; }
        if (h->dma_fault || h->configuration_failed) { ret = -EIO; break; }
        if (h->file_active || !(readl(h->regs + STATUS) & READY)) { ret = -EBUSY; break; }
        if (readl(h->regs + ALGORITHM) == 2 && length > (U64_MAX >> 3)) {
            ret = -EFBIG; break;
        }
        writel(lower_32_bits(length), h->regs + LENGTH_LO);
        writel(upper_32_bits(length), h->regs + LENGTH_HI);
        writel(1, h->regs + CONTROL);
        status = readl(h->regs + STATUS);
        if (status & ERROR) { ret = -EIO; break; }
        h->remaining = length; h->file_active = true;
        break;
    case HASH_TRANSFER:
        if (copy_from_user(&count, user, sizeof(count))) { ret = -EFAULT; break; }
        ret = hash_transfer(h, count);
        break;
    case HASH_RESULT:
        if (h->dma_fault) { ret = -EIO; break; }
        if (!h->file_active || h->remaining) { ret = -EINVAL; break; }
        ret = readl_poll_timeout(h->regs + STATUS, status, status & (DONE | ERROR), 10, 10000000);
        if (ret) {
            stop_ret = hash_stop(h, false);
            if (stop_ret) ret = stop_ret;
            break;
        }
        result.status = status; result.error = readl(h->regs + ERROR_CODE);
        for (i = 0; i < 8; i++) {
            word = readl(h->regs + DIGEST + 4*i);
            for (j = 0; j < 4; j++) result.digest[4*i+j] = word >> (8*j);
        }
        result.cycles = readl(h->regs + CYCLES_LO);
        result.cycles |= (u64)readl(h->regs + CYCLES_HI) << 32;
        h->file_active = false;
        ret = copy_to_user(user, &result, sizeof(result)) ? -EFAULT : 0;
        break;
    case HASH_SWITCH:
        if (copy_from_user(&request, user, sizeof(request))) { ret = -EFAULT; break; }
        ret = hash_switch_image(h, &request);
        if (!ret && copy_to_user(user, &request, sizeof(request))) ret = -EFAULT;
        break;
    case HASH_ABORT:
        ret = hash_stop(h, true);
        break;
    default:
        ret = -ENOTTY;
    }
    mutex_unlock(&h->lock);
    return ret;
}

static int hash_open(struct inode *inode, struct file *file)
{
    struct hash_device *h = container_of(file->private_data, struct hash_device, misc);
    u32 status;
    int ret;

    if (atomic_cmpxchg(&h->opened, 0, 1))
        return -EBUSY;
    file->private_data = h;
    mutex_lock(&h->lock);
    if (h->configuration_failed || h->dma_fault) {
        /* Allow explicit recovery ioctls, never release isolation on reopen. */
        mutex_unlock(&h->lock);
        return 0;
    }
    /* Boot image is already programmed; release its initially isolated RP. */
    writel(8, h->regs + CONTROL);
    ret = readl_poll_timeout(h->regs + STATUS, status, status & READY, 10, 100000);
    if (ret) {
        writel(4, h->regs + CONTROL);
        atomic_set(&h->opened, 0);
    }
    mutex_unlock(&h->lock);
    return ret;
}

static int hash_release(struct inode *inode, struct file *file)
{
    struct hash_device *h = file->private_data;
    int ret;

    mutex_lock(&h->lock);
    ret = hash_stop(h, false);
    atomic_set(&h->opened, 0);
    mutex_unlock(&h->lock);
    return ret;
}

static int hash_mmap(struct file *file, struct vm_area_struct *vma)
{
    struct hash_device *h = file->private_data;
    if (vma->vm_pgoff || vma->vm_end - vma->vm_start != BUFFER_SIZE)
        return -EINVAL;
    return dma_mmap_coherent(h->dma_dev, vma, h->buffer, h->dma_address, BUFFER_SIZE);
}

static const struct file_operations hash_operations = {
    .owner = THIS_MODULE, .open = hash_open, .release = hash_release,
    .unlocked_ioctl = hash_ioctl, .compat_ioctl = hash_ioctl, .mmap = hash_mmap,
};

static int hash_probe(struct platform_device *pdev)
{
    struct hash_device *h;
    struct device_node *manager_node;
    int ret;

    h = devm_kzalloc(&pdev->dev, sizeof(*h), GFP_KERNEL);
    if (!h) return -ENOMEM;
    h->dev = &pdev->dev;
    h->regs = devm_platform_ioremap_resource(pdev, 0);
    if (IS_ERR(h->regs)) return PTR_ERR(h->regs);
    if (readl(h->regs + VERSION) != 0x10000) return -ENODEV;
    h->tx = dma_request_chan(h->dev, "tx");
    if (IS_ERR(h->tx)) return dev_err_probe(h->dev, PTR_ERR(h->tx), "DMA channel unavailable\n");
    h->dma_dev = dmaengine_get_dma_device(h->tx);
    manager_node = of_parse_phandle(pdev->dev.of_node, "fpga-mgr", 0);
    if (!manager_node) { ret = -EINVAL; goto release_dma; }
    h->manager = of_fpga_mgr_get(manager_node);
    of_node_put(manager_node);
    if (IS_ERR(h->manager)) { ret = PTR_ERR(h->manager); goto release_dma; }
    h->buffer = dma_alloc_coherent(h->dma_dev, BUFFER_SIZE, &h->dma_address, GFP_KERNEL);
    if (!h->buffer) { ret = -ENOMEM; goto put_manager; }
    init_completion(&h->completion); mutex_init(&h->lock); atomic_set(&h->opened, 0);
    h->misc.minor = MISC_DYNAMIC_MINOR; h->misc.name = "hash-accel";
    h->misc.fops = &hash_operations; h->misc.parent = h->dev; h->misc.mode = 0600;
    platform_set_drvdata(pdev, h);
    ret = misc_register(&h->misc);
    if (!ret) return 0;
    dma_free_coherent(h->dma_dev, BUFFER_SIZE, h->buffer, h->dma_address);
put_manager:
    fpga_mgr_put(h->manager);
release_dma:
    dma_release_channel(h->tx);
    return ret;
}

static void hash_remove_common(struct platform_device *pdev)
{
    struct hash_device *h = platform_get_drvdata(pdev);
    int ret;

    misc_deregister(&h->misc);
    ret = hash_stop(h, false);
    writel(4, h->regs + CONTROL);
    if (ret) {
        /* An existing fault pins the module against normal rmmod. A new
         * teardown failure must not return potentially active DMA resources
         * to their allocators. Forced platform-device removal is unsupported.
         */
        dev_crit(h->dev, "DMA not quiesced during removal; resources retained, reboot required\n");
        fpga_mgr_put(h->manager);
        return;
    }
    dma_free_coherent(h->dma_dev, BUFFER_SIZE, h->buffer, h->dma_address);
    fpga_mgr_put(h->manager); dma_release_channel(h->tx);
}

#if LINUX_VERSION_CODE < KERNEL_VERSION(6, 11, 0)
static int hash_remove(struct platform_device *pdev) { hash_remove_common(pdev); return 0; }
#else
static void hash_remove(struct platform_device *pdev) { hash_remove_common(pdev); }
#endif

static const struct of_device_id hash_match[] = {
    { .compatible = "core-forge,hash-accelerator-1.0" }, {}
};
MODULE_DEVICE_TABLE(of, hash_match);
static struct platform_driver hash_driver = {
    .probe = hash_probe, .remove = hash_remove,
    .driver = { .name = "hash-accel", .of_match_table = hash_match,
                .suppress_bind_attrs = true },
};
module_platform_driver(hash_driver);
MODULE_LICENSE("GPL");
MODULE_DESCRIPTION("Static DFX hash shell, coherent AXI DMA buffer and PCAP switching");
