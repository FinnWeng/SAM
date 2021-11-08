# Vision Transformer with SAM

This repo is basically trying to reproduce result of "WHEN VISION TRANSFORMERS OUTPERFORM RESNETS WITHOUT PRE-TRAINING OR STRONG DATA AUGMENTATIONS".

It is using Sharpness-Aware Minimization(SAM) on ViT.

SAM paper provides an official implementation using JAX and an also implementation using Pytorch.

Based on JAX implementation, I implemented Tensorflow version.

# First Try
<p align="center">
    <a href="url"><img src="https://github.com/FinnWeng/SAM/blob/main/common/SAM_vs_no_SAM_and_vit_with_fail_representation.PNG" height="388" width="632"></a>
</p>

Above is the result compare ViT model with/without SAM for CIFAR 10 classification. 

ViT is famous for it is very hard to train(origin version). 

My version add some representation MLP before head layer, but it still can't converge(blue line).

And with SAM(orange line), it gradually converge. 