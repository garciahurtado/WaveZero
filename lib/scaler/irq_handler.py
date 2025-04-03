class IrqHandler():
    display: None
    scaler: None
    dma: None

    @staticmethod
    # @micropython.viper
    def irq_handler(ch):
        ch_number = int(ch.channel)
        my_irq = ch.irq()
        flags = my_irq.flags()

        if DEBUG_IRQ:
            print(f"(((( IRQ RAISED BY CH {ch_number} ))))")
            print("IRQ:")
            print('\t\t' + str(ch))
        if ch_number == 2:
            return IrqHandler.dma.irq_read_addr(ch)
        elif ch_number == 4:
            return IrqHandler.dma.irq_end_color_row(ch)
        elif ch_number == 5:
            return IrqHandler.dma.irq_px_read(ch)
        elif ch_number == 7:
            return IrqHandler.dma.irq_h_scale(ch)
        else:
            return False

    @staticmethod
    def irq_handler_display(ch):
        channel = int(ch.channel)
        if channel == 0:
            return IrqHandler.display.irq_render(ch)
        elif channel == 1:
            return IrqHandler.display.irq_render_ctrl(ch)



