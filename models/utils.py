# -*- coding: utf-8 -*-
import torch
import torch.nn as nn
from bounding_box import BoxList
from boxlist_ops import cat_boxlist,boxlist_nms


class get_detector(nn.Module):
    def __init__(self, cfg):
        super(get_detector,self).__init__()
        self.nms_thresh = cfg['NMS_thresh']
        self.conf_thresh = cfg['conf_thres']
        self.nms_thresh_topN = cfg['nms_thresh_topN']
        self.num_classes = cfg['num_classes']
        pass
    
    def forward(self, locations, pred_cls, pred_boxes, pred_centerness, image_sizes):
        res_boxes = []
        
        for l, c, b, m in zip(locations, pred_cls, pred_boxes, pred_centerness):
            res_boxes.append(self.single_fmps_process(l, c, b, m, image_sizes))
            
        boxlists = list(zip(*res_boxes))
        boxlists = [cat_boxlist(boxlist) for boxlist in boxlists]
        boxlists = self.select_over_all_levels(boxlists)
        return boxlists

    
    def select_over_all_levels(self, boxlists):
        num_imgs = len(boxlists)
        results = []
        
        for i in range(num_imgs):
            scores = boxlists[i].get_field("scores")
            labels = boxlists[i].get_field("labels")
            boxes = boxlists[i].bbox
            boxlist = boxlists[i]
            result = []
            # skip the background
            for j in range(1, self.num_classes+1):
                idx = (labels == j).nonzero().view(-1)
                scores_j = scores[idx]
                boxes_j = boxes[idx, :].view(-1, 4)
               
                boxlist_for_class = BoxList(boxes_j, boxlist.size, mode="xyxy")
                boxlist_for_class.add_field("scores", scores_j)
                boxlist_for_class = boxlist_nms(boxlist_for_class, self.nms_thresh, score_field='scores')
                num_labels = len(boxlist_for_class)
                labels = torch.full((num_labels,), j, dtype=torch.int64, device=scores.device)
                boxlist_for_class.add_field('labels', labels)
                result.append(boxlist_for_class)

            #
            result = cat_boxlist(result)
            number_of_detections = len(result)
            # Limit to max_per_image detections **over all classes**
            if number_of_detections > self.nms_thresh_topN > 0:
                cls_scores = result.get_field("scores")
                image_thresh, _ = torch.kthvalue(
                    cls_scores.cpu(),
                    number_of_detections - self.nms_thresh_topN + 1
                )
                keep = cls_scores >= image_thresh.item()
                keep = torch.nonzero(keep).squeeze(1)
                result = result[keep]
            results.append(result)
        return results
               

    def single_fmps_process(self, location, pred_cls, pred_box, pred_centerness, image_sizes):
        B, H, W, C = pred_cls.shape
       
        pred_cls = pred_cls.view(B, -1, C).sigmoid()  
        pred_box = pred_box.view(B, -1, 4)            
        pred_centerness = pred_centerness.view(B, -1).sigmoid() 
        
        cls_mask = pred_cls > self.conf_thresh           
        cls_mask_top_n = cls_mask.view(B, -1).sum(1)           
        cls_mask_top_n = cls_mask_top_n.clamp(max=self.nms_thresh_topN)
        # multiply the classification scores with centerness scores
        pred_cls =  pred_cls * pred_centerness[:, :, None]         
        
        res = []
        for b in range(B):
            per_cls = pred_cls[b]     
            per_cls_mask = cls_mask[b]   
            per_cls = per_cls[per_cls_mask]  
            
            per_cls_mask_nonzeros = per_cls_mask.nonzero() 
                 
            per_box_loc = per_cls_mask_nonzeros[:, 0]
            per_box_cls = per_cls_mask_nonzeros[:, 1] + 1  # class index
             

            per_box = pred_box[b]
            per_box = per_box[per_box_loc]
            per_location = location[per_box_loc]
            per_cls_mask_top_n = cls_mask_top_n[b]

            if per_cls_mask.sum().item() > per_cls_mask_top_n.item():
                per_cls, top_k_idx = per_cls.topk(per_cls_mask_top_n, sorted=False)
                per_box_cls = per_box_cls[top_k_idx]
                per_box = per_box[top_k_idx]
                per_location = per_location[top_k_idx]

            detections = torch.stack([                  
                    per_location[:, 0] - per_box[:, 0],
                    per_location[:, 1] - per_box[:, 1],
                    per_location[:, 0] + per_box[:, 2],
                    per_location[:, 1] + per_box[:, 3],                
                    ],dim=1)
         
            h,w  = image_sizes[0]
            box_list = BoxList(detections, (w,h), mode='xyxy')
            box_list.add_field('labels', per_box_cls)
            box_list.add_field('scores', per_cls)  #  * centerness < 0.5
            box_list = box_list.clip_to_image(remove_empty=False)      
            res.append(box_list)
            
        return res
            


def one_hot_embedding(labels, num_classes):
    '''Embedding labels to one-hot form.

    Args:
      labels: (LongTensor) class labels, sized [N,].
      num_classes: (int) number of classes.

    Returns:
      (tensor) encoded labels, sized [N,#classes].
    '''
    y = torch.eye(num_classes, device=labels.device)  # [D,D]
    return y[labels]   

