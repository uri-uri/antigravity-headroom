class BaseCompressor:
    def compress(self, text: str, **kwargs) -> str:
        """
        Compresses the input text and returns the compressed version.
        
        Args:
            text (str): The raw input content to compress.
            **kwargs: Extra parameters for configuration.
            
        Returns:
            str: Compressed content.
        """
        raise NotImplementedError("Compressors must implement compress()")
