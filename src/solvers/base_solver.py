import cv2

class BaseSolver:
    def __init__ (self, config):
        self.set_config(config)
    
    def set_config (self, config):
        self.config = config
    
    def set_img (self, img):
        self.img = img
        self.img_dims = (img.shape[0], img.shape[1])