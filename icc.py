#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Tue Mar 30 18:26:54 2021

@author: davood
"""





from __future__ import division

import numpy as np
import os
import tensorflow as tf
from os import listdir
from os.path import isfile, join

import SimpleITK as sitk

import os.path

import dk_model









LX= LY= LZ = 96
test_shift= LX//4

LXc= LYc= LZc= LX//5

n_feat_0 = 14
depth = 4

ks_0 = 3


n_channel= 1
n_class= 2

X = tf.placeholder("float32", [None, LX, LY, LZ, n_channel])
Y = tf.placeholder("float32", [None, LX, LY, LZ, n_class])
learning_rate = tf.placeholder("float")
p_keep_conv = tf.placeholder("float")


logit_f, _ = dk_model.davood_net(X, ks_0, depth, n_feat_0, n_channel, n_class, p_keep_conv, bias_init=0.001)

predicter = tf.nn.softmax(logit_f)



gpu_ind= 1


os.environ["CUDA_DEVICE_ORDER"]="PCI_BUS_ID"

os.environ["CUDA_VISIBLE_DEVICES"] = str(gpu_ind)

saver = tf.train.Saver(max_to_keep=50)

sess = tf.Session()
sess.run(tf.global_variables_initializer())




keep_test= 1.0






restore_model_path= '/src/model/model_saved_13_9678.ckpt'
saver.restore(sess, restore_model_path)










#  No interp

test_shift= 16

#######################    test    ##########################################

test_dir= '/src/test_images/'

seg_dir= test_dir + 'segmentations/'
os.makedirs( seg_dir , exist_ok=True)


img_files = [f for f in listdir(test_dir) if isfile( join(test_dir, f) ) ]
img_files.sort()

n_cases= len(img_files)

normalize_by_mask= True

# dice_c= np.zeros( (n_cases, 1) )

for i_file in range(n_cases):

    print('Running the segmentation on ', img_files[i_file] )
    
    vol = sitk.ReadImage(test_dir+ img_files[i_file] )
    vol_np = sitk.GetArrayFromImage(vol)
    vol_np = np.transpose(vol_np, [2, 1, 0])
    
    if np.mean(vol_np==1)  + np.mean(vol_np==0)>0.999:
        
        print('   This seems to be a segmentation file, not an image. Skipping!')
        
    else:
        
        vol_origin= vol.GetOrigin()
        vol_direction= vol.GetDirection()
        
        vol_spacing= vol.GetSpacing()
        vol_size   = vol.GetSize()
        
        temp = vol_np[vol_np > 0]
        vol_mean= temp.mean()
        vol_std= temp.std()
        
        # vol= dk_seg.resample3d(vol, vol_spacing, desired_spacing, sitk.sitkBSpline)
        vol_np = sitk.GetArrayFromImage(vol)
        vol_np = np.transpose(vol_np, [2, 1, 0])
        
        vol_np = vol_np / vol_std
        
        SX, SY, SZ= vol_np.shape
        
        under_sized= False
        if SX<=LX or SY<=LY or SZ<=LZ:
            under_sized= True
            SX0, SY0, SZ0= SX, SY, SZ
            temp= vol_np.copy()
            vol_np= np.zeros((LX*2+SX0,LY*2+SY0,LZ*2+SZ0))
            vol_np[LX:LX+SX0, LY:LY+SY0, LZ:LZ+SZ0]= temp.copy()
            SX, SY, SZ= vol_np.shape
        
        lx_list= np.squeeze( np.concatenate(  (np.arange(0, SX-LX, test_shift)[:,np.newaxis] , np.array([SX-LX])[:,np.newaxis] )  ) .astype(np.int) )
        ly_list= np.squeeze( np.concatenate(  (np.arange(0, SY-LY, test_shift)[:,np.newaxis] , np.array([SY-LY])[:,np.newaxis] )  ) .astype(np.int) )
        lz_list= np.squeeze( np.concatenate(  (np.arange(0, SZ-LZ, test_shift)[:,np.newaxis] , np.array([SZ-LZ])[:,np.newaxis] )  ) .astype(np.int) )
        
        y_tr_pr_sum = np.zeros((SX, SY, SZ, n_class))
        y_tr_pr_cnt = np.zeros((SX, SY, SZ))
    
        for lx in lx_list:
            for ly in ly_list:
                for lz in lz_list:
                                   
                    if np.max(vol_np[lx + LXc:lx + LX - LXc, ly + LYc:ly + LY - LYc, lz + LZc:lz + LZ - LZc]) > 0:
                        
                        batch_x = vol_np[lx:lx + LX, ly:ly + LY, lz:lz + LZ].copy()
                        batch_x = batch_x[np.newaxis,:,:,:,np.newaxis]
                        
                        pred_temp = sess.run(predicter,  feed_dict={X: batch_x, p_keep_conv: keep_test})
                        y_tr_pr_sum[lx:lx + LX, ly:ly + LY, lz:lz + LZ,:] += pred_temp[0, :, :, :, :]
                        y_tr_pr_cnt[lx:lx + LX, ly:ly + LY, lz:lz + LZ] += 1
        
        if under_sized:
            y_tr_pr_sum= y_tr_pr_sum[LX:LX+SX0, LY:LY+SY0, LZ:LZ+SZ0,:]
            y_tr_pr_cnt= y_tr_pr_cnt[LX:LX+SX0, LY:LY+SY0, LZ:LZ+SZ0]
            vol_np= vol_np[LX:LX+SX0, LY:LY+SY0, LZ:LZ+SZ0]
            
        y_tr_pr_c = np.argmax(y_tr_pr_sum, axis=-1)
        y_tr_pr_c[y_tr_pr_cnt == 0] = 0
        
        y_tr_pr_c= (y_tr_pr_c>0.5).astype(np.int8)
        
        y_tr_pr_c= np.transpose(y_tr_pr_c, [2, 1, 0])
        y_tr_pr_c= sitk.GetImageFromArray(y_tr_pr_c)
        # y_tr_pr_c.SetSpacing(desired_spacing)
        
        # y_tr_pr_c= dk_seg.resample3d(y_tr_pr_c, desired_spacing, vol_spacing, sitk.sitkNearestNeighbor)
        
        # y_tr_pr_c= sitk.GetArrayFromImage(y_tr_pr_c)
        # y_tr_pr_c= (y_tr_pr_c>0.5).astype(np.int8)
        # y_tr_pr_c= sitk.GetImageFromArray(y_tr_pr_c)
        
        y_tr_pr_c.SetSpacing(vol_spacing)
        y_tr_pr_c.SetOrigin(vol_origin)
        y_tr_pr_c.SetDirection(vol_direction)
        
        
        image_name= img_files[i_file]
        base_name, extension= image_name.split('.', 1)
        seg_name= base_name + '_segmentation.' + extension
        
        print('writing,  ',  seg_dir+ seg_name )
        
        
        sitk.WriteImage(y_tr_pr_c, seg_dir+ seg_name )
    














