#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Mon Jul  1 00:49:46 2019

@author: wei
"""

config = {
        ## model
        'num_classes': 1,
        'classes': ['background', 'car',],
        'img_size': 416,
        
        ## train
        'weight_decay': 0.0001,
        'images_root': r'/home/chi_zhang/mengfei/_mf/UCAS/images',
        'train_path': r'/home/chi_zhang/mengfei/_mf/UCAS/train.txt',
        'test_path': r'/home/chi_zhang/mengfei/_mf/UCAS/test.txt',
        'ckpt_name': 'checkpoint.pth',
        
        ## focal loss
        'alpha': 0.25,
        'gamma': 2.0,
        
        ## demo
        'conf_thres':0.4,
        'nms_thresh_topN':100,
        'NMS_thresh':0.4,
        
        }