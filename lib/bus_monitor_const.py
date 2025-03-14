# RP2040 Bus Controller Register Constants

# Register Base Address
BUSCTRL_BASE = 0x40068000  # Corrected base address

# Register Offsets
BUS_PRIORITY = 0x00
BUS_PRIORITY_ACK = 0x04
PERFCTR_EN = 0x08
PERFCTR0 = 0x0C
PERFSEL0 = 0x10
PERFCTR1 = 0x14
PERFSEL1 = 0x18
PERFCTR2 = 0x1C
PERFSEL2 = 0x20
PERFCTR3 = 0x24
PERFSEL3 = 0x28

# Register Addresses
BUS_PRIORITY_ADDR = BUSCTRL_BASE + BUS_PRIORITY
BUS_PRIORITY_ACK_ADDR = BUSCTRL_BASE + BUS_PRIORITY_ACK
PERFCTR_EN_ADDR = BUSCTRL_BASE + PERFCTR_EN
PERFCTR0_ADDR = BUSCTRL_BASE + PERFCTR0
PERFSEL0_ADDR = BUSCTRL_BASE + PERFSEL0
PERFCTR1_ADDR = BUSCTRL_BASE + PERFCTR1
PERFSEL1_ADDR = BUSCTRL_BASE + PERFSEL1
PERFCTR2_ADDR = BUSCTRL_BASE + PERFCTR2
PERFSEL2_ADDR = BUSCTRL_BASE + PERFSEL2
PERFCTR3_ADDR = BUSCTRL_BASE + PERFCTR3
PERFSEL3_ADDR = BUSCTRL_BASE + PERFSEL3

# Performance Counter Event Values
PERF_EVENTS = {
    # SIOB_PROC1 Events (Core 1)
    0x00: "SIOB_PROC1_STALL_UPSTREAM",
    0x01: "SIOB_PROC1_STALL_DOWNSTREAM",
    0x02: "SIOB_PROC1_ACCESS_CONTESTED",
    0x03: "SIOB_PROC1_ACCESS",

    # SIOB_PROC0 Events (Core 0)
    0x04: "SIOB_PROC0_STALL_UPSTREAM",
    0x05: "SIOB_PROC0_STALL_DOWNSTREAM",
    0x06: "SIOB_PROC0_ACCESS_CONTESTED",
    0x07: "SIOB_PROC0_ACCESS",

    # APB Events
    0x08: "APB_STALL_UPSTREAM",
    0x09: "APB_STALL_DOWNSTREAM",
    0x0A: "APB_ACCESS_CONTESTED",
    0x0B: "APB_ACCESS",

    # FASTPERI Events
    0x0C: "FASTPERI_STALL_UPSTREAM",
    0x0D: "FASTPERI_STALL_DOWNSTREAM",
    0x0E: "FASTPERI_ACCESS_CONTESTED",
    0x0F: "FASTPERI_ACCESS",

    # SRAM9 Events
    0x10: "SRAM9_STALL_UPSTREAM",
    0x11: "SRAM9_STALL_DOWNSTREAM",
    0x12: "SRAM9_ACCESS_CONTESTED",
    0x13: "SRAM9_ACCESS",

    # SRAM8 Events
    0x14: "SRAM8_STALL_UPSTREAM",
    0x15: "SRAM8_STALL_DOWNSTREAM",
    0x16: "SRAM8_ACCESS_CONTESTED",
    0x17: "SRAM8_ACCESS",

    # SRAM7 Events
    0x18: "SRAM7_STALL_UPSTREAM",
    0x19: "SRAM7_STALL_DOWNSTREAM",
    0x1A: "SRAM7_ACCESS_CONTESTED",
    0x1B: "SRAM7_ACCESS",

    # SRAM6 Events
    0x1C: "SRAM6_STALL_UPSTREAM",
    0x1D: "SRAM6_STALL_DOWNSTREAM",
    0x1E: "SRAM6_ACCESS_CONTESTED",
    0x1F: "SRAM6_ACCESS",

    # SRAM5 Events
    0x20: "SRAM5_STALL_UPSTREAM",
    0x21: "SRAM5_STALL_DOWNSTREAM",
    0x22: "SRAM5_ACCESS_CONTESTED",
    0x23: "SRAM5_ACCESS",

    # SRAM4 Events
    0x24: "SRAM4_STALL_UPSTREAM",
    0x25: "SRAM4_STALL_DOWNSTREAM",
    0x26: "SRAM4_ACCESS_CONTESTED",
    0x27: "SRAM4_ACCESS",

    # SRAM3 Events
    0x28: "SRAM3_STALL_UPSTREAM",
    0x29: "SRAM3_STALL_DOWNSTREAM",
    0x2A: "SRAM3_ACCESS_CONTESTED",
    0x2B: "SRAM3_ACCESS",

    # SRAM2 Events
    0x2C: "SRAM2_STALL_UPSTREAM",
    0x2D: "SRAM2_STALL_DOWNSTREAM",
    0x2E: "SRAM2_ACCESS_CONTESTED",
    0x2F: "SRAM2_ACCESS",

    # SRAM1 Events
    0x30: "SRAM1_STALL_UPSTREAM",
    0x31: "SRAM1_STALL_DOWNSTREAM",
    0x32: "SRAM1_ACCESS_CONTESTED",
    0x33: "SRAM1_ACCESS",

    # SRAM0 Events
    0x34: "SRAM0_STALL_UPSTREAM",
    0x35: "SRAM0_STALL_DOWNSTREAM",
    0x36: "SRAM0_ACCESS_CONTESTED",
    0x37: "SRAM0_ACCESS",

    # XIP_MAIN1 Events
    0x38: "XIP_MAIN1_STALL_UPSTREAM",
    0x39: "XIP_MAIN1_STALL_DOWNSTREAM",
    0x3A: "XIP_MAIN1_ACCESS_CONTESTED",
    0x3B: "XIP_MAIN1_ACCESS",

    # XIP_MAIN0 Events
    0x3C: "XIP_MAIN0_STALL_UPSTREAM",
    0x3D: "XIP_MAIN0_STALL_DOWNSTREAM",
    0x3E: "XIP_MAIN0_ACCESS_CONTESTED",
    0x3F: "XIP_MAIN0_ACCESS",

    # ROM Events
    0x40: "ROM_STALL_UPSTREAM",
    0x41: "ROM_STALL_DOWNSTREAM",
    0x42: "ROM_ACCESS_CONTESTED",
    0x43: "ROM_ACCESS"
}

# Descriptions of event categories
EVENT_DESCRIPTIONS = {
    "ACCESS": "Count of accesses",
    "ACCESS_CONTESTED": "Count of accesses that previously stalled due to contention",
    "STALL_DOWNSTREAM": "Count of cycles where masters stalled due to downstream bus stalls",
    "STALL_UPSTREAM": "Count of cycles where masters stalled for any reason"
}

# Human-readable categories of events
EVENT_CATEGORIES = {
    "PROC0": [0x04, 0x05, 0x06, 0x07],  # Core 0 events
    "PROC1": [0x00, 0x01, 0x02, 0x03],  # Core 1 events
    "SRAM": list(range(0x10, 0x38)),  # All SRAM events
    "XIP": list(range(0x38, 0x40)),  # XIP (execute in place) flash events
    "ROM": [0x40, 0x41, 0x42, 0x43],  # ROM events
    "PERIPH": list(range(0x08, 0x10))  # Peripheral events (APB + FASTPERI)
}

# Common event combinations for typical use cases
COMMON_PRESETS = {
    # Core Activity - Monitor CPU access patterns
    "core_activity": [0x07, 0x03, 0x06, 0x02],
    # PROC0_ACCESS, PROC1_ACCESS, PROC0_ACCESS_CONTESTED, PROC1_ACCESS_CONTESTED

    # Memory Access - Monitor different memory regions
    "memory_access": [0x37, 0x3F, 0x43, 0x0F],  # SRAM0_ACCESS, XIP_MAIN0_ACCESS, ROM_ACCESS, FASTPERI_ACCESS

    # Memory Contention - Track contested access to memory
    "memory_contested": [0x36, 0x3E, 0x42, 0x0E],
    # SRAM0_ACCESS_CONTESTED, XIP_MAIN0_ACCESS_CONTESTED, ROM_ACCESS_CONTESTED, FASTPERI_ACCESS_CONTESTED

    # Core 0 Performance - All Core 0 metrics
    "core0_detail": [0x04, 0x05, 0x06, 0x07],
    # PROC0_STALL_UPSTREAM, PROC0_STALL_DOWNSTREAM, PROC0_ACCESS_CONTESTED, PROC0_ACCESS

    # Core 1 Performance - All Core 1 metrics
    "core1_detail": [0x00, 0x01, 0x02, 0x03],
    # PROC1_STALL_UPSTREAM, PROC1_STALL_DOWNSTREAM, PROC1_ACCESS_CONTESTED, PROC1_ACCESS

    # Flash Performance - Monitor XIP (execute in place) flash memory
    "flash_perf": [0x3C, 0x3D, 0x3E, 0x3F],
    # XIP_MAIN0_STALL_UPSTREAM, XIP_MAIN0_STALL_DOWNSTREAM, XIP_MAIN0_ACCESS_CONTESTED, XIP_MAIN0_ACCESS

    # SRAM Bank 0 - Monitor first SRAM bank
    "sram0": [0x34, 0x35, 0x36, 0x37],
    # SRAM0_STALL_UPSTREAM, SRAM0_STALL_DOWNSTREAM, SRAM0_ACCESS_CONTESTED, SRAM0_ACCESS

    # Memory Bottlenecks - Focus on stalls across different memory regions
    "memory_stalls": [0x34, 0x3C, 0x40, 0x0C],
    # SRAM0_STALL_UPSTREAM, XIP_MAIN0_STALL_UPSTREAM, ROM_STALL_UPSTREAM, FASTPERI_STALL_UPSTREAM

    # Multicore Performance - Compare Core 0 vs Core 1 key metrics
    "multicore": [0x07, 0x03, 0x04, 0x00],  # PROC0_ACCESS, PROC1_ACCESS, PROC0_STALL_UPSTREAM, PROC1_STALL_UPSTREAM

    # DMA Activity - Track memory activity (useful when DMA is active)
    "dma_impact": [0x36, 0x3E, 0x04, 0x00],
    # SRAM0_ACCESS_CONTESTED, XIP_MAIN0_ACCESS_CONTESTED, PROC0_STALL_UPSTREAM, PROC1_STALL_UPSTREAM

    # Peripheral Access - Monitor peripheral buses
    "peripherals": [0x0B, 0x0F, 0x0A, 0x0E],
    # APB_ACCESS, FASTPERI_ACCESS, APB_ACCESS_CONTESTED, FASTPERI_ACCESS_CONTESTED

    # Memory Bandwidth - Track all types of memory access
    "mem_bandwidth": [0x37, 0x3F, 0x43, 0x2B],  # SRAM0_ACCESS, XIP_MAIN0_ACCESS, ROM_ACCESS, SRAM3_ACCESS

    # Core0 vs Flash - Analyze relationship between CPU0 and Flash
    "core0_flash": [0x07, 0x06, 0x3F, 0x3E],
    # PROC0_ACCESS, PROC0_ACCESS_CONTESTED, XIP_MAIN0_ACCESS, XIP_MAIN0_ACCESS_CONTESTED

    # Overall System - General overview of system performance
    "system_overview": [0x07, 0x03, 0x3F, 0x37],  # PROC0_ACCESS, PROC1_ACCESS, XIP_MAIN0_ACCESS, SRAM0_ACCESS

    # Flash Bottlenecks - Detailed analysis of flash memory issues
    "flash_bottlenecks": [0x3C, 0x3D, 0x3E, 0x3F],
    # XIP_MAIN0_STALL_UPSTREAM, XIP_MAIN0_STALL_DOWNSTREAM, XIP_MAIN0_ACCESS_CONTESTED, XIP_MAIN0_ACCESS

    # Cache Performance - Flash access patterns (indicative of cache performance)
    "cache_perf": [0x3F, 0x3E, 0x3D, 0x3C],
    # XIP_MAIN0_ACCESS, XIP_MAIN0_ACCESS_CONTESTED, XIP_MAIN0_STALL_DOWNSTREAM, XIP_MAIN0_STALL_UPSTREAM

    # Graphics/Display - Monitor memory patterns during graphics operations
    "graphics": [0x37, 0x3F, 0x36, 0x3E],
    # SRAM0_ACCESS, XIP_MAIN0_ACCESS, SRAM0_ACCESS_CONTESTED, XIP_MAIN0_ACCESS_CONTESTED

    # Audio Processing - Monitor DMA and memory during audio processing
    "audio": [0x37, 0x0F, 0x36, 0x0E],
    # SRAM0_ACCESS, FASTPERI_ACCESS, SRAM0_ACCESS_CONTESTED, FASTPERI_ACCESS_CONTESTED

    # Communication (SPI/I2C/UART) - Monitor peripheral and CPU activity
    "comm_periph": [0x0F, 0x0E, 0x07, 0x06],
    # FASTPERI_ACCESS, FASTPERI_ACCESS_CONTESTED, PROC0_ACCESS, PROC0_ACCESS_CONTESTED

    # File Operations - Monitor flash activity during file operations
    "filesystem": [0x3F, 0x3E, 0x3D, 0x37],
    # XIP_MAIN0_ACCESS, XIP_MAIN0_ACCESS_CONTESTED, XIP_MAIN0_STALL_DOWNSTREAM, SRAM0_ACCESS

    # Real-time Control - Monitor deterministic performance
    "realtime": [0x07, 0x04, 0x0F, 0x0C],
    # PROC0_ACCESS, PROC0_STALL_UPSTREAM, FASTPERI_ACCESS, FASTPERI_STALL_UPSTREAM

    # Machine Learning - Memory and CPU patterns during ML inference
    "ml_inference": [0x37, 0x3F, 0x07, 0x06],  # SRAM0_ACCESS, XIP_MAIN0_ACCESS, PROC0_ACCESS, PROC0_ACCESS_CONTESTED

    # Wireless (BLE/WiFi) - Monitor activity during wireless operations
    "wireless": [0x0F, 0x37, 0x07, 0x03],  # FASTPERI_ACCESS, SRAM0_ACCESS, PROC0_ACCESS, PROC1_ACCESS
}
