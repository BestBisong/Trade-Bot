class BaseStrategy:
    def signal(self, df):
        """
        Base method for all strategies. 
        Must be overridden by subclasses.
        """
        raise NotImplementedError("Subclasses must implement the signal method")