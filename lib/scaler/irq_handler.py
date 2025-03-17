from scaler.const import DEBUG_IRQ
import micropython

class IrqHandler():
    display: None
    scaler: None
    dma: None

    @staticmethod
    # @micropython.viper
    def irq_handler(ch):
        channel = int(ch.channel)
        if DEBUG_IRQ:
            print(f"(((( IRQ RAISED BY CH {channel} ))))")
            print(":::IRQ:::")
            print(ch)

        if channel == 0:
            return IrqHandler.display.irq_render(ch)
        elif channel == 1:
            return IrqHandler.display.irq_render_ctrl(ch)
        elif channel == 2:
            return IrqHandler.dma.irq_end_read_addr(ch)
        elif channel == 4:
            return IrqHandler.dma.irq_end_row(ch)
        elif channel == 5:
            return IrqHandler.dma.irq_px_read(ch)
        elif channel == 7:
            return IrqHandler.dma.irq_h_scale(ch)
        else:
            return ch


