from progressbar import ProgressBar, ETA, ReverseBar, Bar


class DefaultProgressBar(ProgressBar):
    """
    progressbar with predefined parameters
    """
    def __init__(self, maxval, caption=''):
        widgets = [caption, Bar('>'), ' ', ETA(), ' ', ReverseBar('<')]
        super(DefaultProgressBar, self).__init__(widgets=widgets, maxval=maxval)


def progress(gen, caption='', pb_class=DefaultProgressBar):
    """
    Make a generator that displays a progress bar from
    generator gen, set caption and choose the class to
    use (DefaultProgressBar by default)

    Generator should have __len__ method returning it's
    size.

    Progress bar class constructor should take two
    parameters:
      * generator size
      * progress bar caption.

    It also should have start, update and finish methods.
    """
    pbar = pb_class(len(gen), caption).start() if pb_class else None
    i = 0
    for elem in gen:
        if pbar:
            pbar.update(i)
        i += 1
        yield(elem)
    if pbar:
        pbar.finish()
