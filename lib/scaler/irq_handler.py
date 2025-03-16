from scaler.const import DEBUG_IRQ


class IrqHandler():
    display: None
    scaler: None
    dma: None

    @staticmethod
    def irq_handler(ch):
        if DEBUG_IRQ:
            print(f"(((( IRQ RAISED BY CH {ch.channel} ))))")

        if ch.channel == 0:
            return IrqHandler.display.irq_render(ch)
        elif ch.channel == 1:
            return IrqHandler.display.irq_render_ctrl(ch)
        elif ch.channel == 2:
            return IrqHandler.dma.irq_end_read_addr(ch)
        elif ch.channel == 4:
            return IrqHandler.dma.irq_end_row(ch)
        elif ch.channel == 5:
            return IrqHandler.dma.irq_px_read(ch)
        elif ch.channel == 7:
            return IrqHandler.dma.irq_h_scale(ch)
