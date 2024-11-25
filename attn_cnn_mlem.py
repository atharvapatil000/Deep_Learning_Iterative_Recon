from skimage.data import brain
from skimage.transform import resize, rescale
import numpy as np
from google.colab.patches import cv2_imshow  # Import cv2_imshow for Colab
import torch

# Custom display function for Colab
def cv2disp(win, ima, xp, yp, sc):
  # Normalize and rescale the image
  normalized_image = rescale(ima, sc, anti_aliasing=False) * 255.0 / (np.max(ima) + 1e-15)
  normalized_image = normalized_image.astype(np.uint8)  # Convert to uint8 for display
  cv2_imshow(normalized_image)  # Use cv2_imshow to display in Colab

def np_to_00torch(np_array): # Converts a NumPy array into a PyTorch tensor.
    return torch.from_numpy(np_array).float().unsqueeze(0).unsqueeze(0) # Adds two singleton dimensions to the tensor. From [H, W] (Height x Width) → [1, H, W] → [1, 1, H, W]. These dimensions can represent batch size (1) and channels (1), which are often required for model input in PyTorch.

def torch_to_np(torch_array): # Converts a PyTorch tensor back into a NumPy array.
    return np.squeeze(torch_array.detach().cpu().numpy()) # Removes singleton dimensions from the array (e.g., [1, 1, H, W] → [H, W]).

# Select computation device (GPU if available, otherwise CPU)
device = torch.device("cuda:0" if torch.cuda.is_available() else "cpu")
print(device)  # Display selected device (e.g., "cuda:0" or "cpu")

# Initialize parameters
nxd = 128  # Number of pixels along one dimension of the square input image
disp_scale = 4  # Scaling factor for display visualization
nrd = int(nxd * 1.42)  # Number of detector bins, approximating the diagonal of the image
nphi = nxd  # Number of projection angles, set equal to the image size

# Load and preprocess the brain image
brainimage = brain()
true_object_np = resize(brainimage[5, 30:-1, 30:-1], (nxd, nxd), anti_aliasing=False)
true_object_torch = np_to_00torch(true_object_np).to(device)

# Display the image
cv2disp('True', true_object_np, 0, 0, disp_scale)

"""This project focuses on the reconstruction of Head CT images using advanced iterative methods and deep learning-based refinement techniques. Computed Tomography (CT) is a widely used medical imaging technique for capturing detailed cross-sectional images of the body, particularly the head, to diagnose various conditions, including trauma, tumors, and other abnormalities. The project implements the Maximum Likelihood Expectation Maximization (MLEM) algorithm as a core reconstruction framework, which is further enhanced using modern neural network architectures like Convolutional Neural Networks (CNNs) and Attention Mechanisms.

The reconstruction begins with sinograms, which represent the raw projection data captured by CT scanners during the imaging process. The MLEM algorithm iteratively updates a reconstruction based on these sinograms, using forward and backward projection operations via a system matrix to minimize the error between the measured and estimated data. The system matrix models the geometry and physics of the CT imaging process, ensuring accurate reconstruction of the head's internal structure.

To improve the quality and accuracy of the reconstructed images, deep learning models are incorporated into the reconstruction pipeline. A traditional CNN model is used to refine the output of each MLEM iteration by capturing local spatial features and removing noise or artifacts. Additionally, an Attention Mechanism is introduced, enabling the network to focus on relevant regions of the image by computing context-aware feature maps. This allows the model to emphasize fine details and improve the reconstruction's overall quality and diagnostic value.

The project is implemented in PyTorch and involves a systematic design where iterative reconstruction is combined with neural network-based refinement. The visualization components ensure intermediate results, such as forward projections, corrections, and reconstruction updates, are displayed for analysis. The system has been designed to process simulated Head CT data, allowing validation of its effectiveness in reconstructing high-quality images.

The work has potential applications in medical diagnostics, particularly in improving the quality of low-dose CT images or reconstructing images with limited projection data. By combining traditional iterative reconstruction methods with deep learning innovations, the project demonstrates a powerful hybrid approach that can lead to faster, more accurate, and artifact-free CT image reconstructions.
"""

def np_to_torch(np_array): # Converts a NumPy array into a PyTorch tensor.
    return torch.from_numpy(np_array).float().unsqueeze(0).unsqueeze(0) # Adds two singleton dimensions to the tensor. From [H, W] (Height x Width) → [1, H, W] → [1, 1, H, W]. These dimensions can represent batch size (1) and channels (1), which are often required for model input in PyTorch.

def torch_to_np(torch_array): # Converts a PyTorch tensor back into a NumPy array.
    return np.squeeze(torch_array.detach().cpu().numpy()) # Removes singleton dimensions from the array (e.g., [1, 1, H, W] → [H, W]).

# Function to create the system matrix
def make_torch_system_matrix(nxd, nrd, nphi):

  # Rows: nrd * nphi represents all the sinogram bins. Columns: nxd * nxd represents all the image pixels (flattened into a 1D array).
  system_matrix = torch.zeros(nrd * nphi, nxd * nxd)  # Creates a large matrix filled with zeros using Pytorch.

  # nxd: Number of pixels along one dimension of the square image.
  # nrd: Number of sinogram bins along the radial direction (e.g 180 bins).
  # nphi: Number of projection angles which defines the number of different orientations used to scan the object.
  for xv in range(nxd):  # Loop over x-coordinates of the image
    for yv in range(nxd):  # Loop over y-coordinates of the image
      for ph in range(nphi):  # Loop Through Each Projection Angle
        # Project the pixel to the detector bin
        # (xv - (nxd * 0.5)): Shifts the x and y-coordinate so the center of the image is at (0, 0).
        yp = -(xv - (nxd * 0.5)) * np.sin(ph * np.pi / nphi) + (yv - (nxd * 0.5)) * np.cos(ph * np.pi / nphi) # Multiplies the coordinates by sin and cos to compute how the pixel is projected onto the detector at angle ph.
        yp_bin = int(yp + nrd / 2.0)  # Maps the computed detector position yp to a discrete detector bin.
        if 0 <= yp_bin < nrd:  # Ensure the bin index is valid
            system_matrix[yp_bin + ph * nrd, xv + yv * nxd] = 1.0  # Sets the value in the system matrix to 1.0 for the corresponding sinogram bin and pixel.

  return system_matrix  # Return the constructed system matrix

"""**Forward Projection Function**"""

def fp_system_torch(image, sys_mat, nxd, nrd, nphi):
  # torch.reshape(image, (nxd * nxd, 1)): Reshapes the 2D image into a 1D column vector of size (nxd * nxd, 1)
  # torch.mm(sys_mat, ...): Performs matrix multiplication (torch.mm) between the system matrix (sys_mat) and the reshaped image vector.
  # torch.reshape(..., (nphi, nrd)): Reshapes the resulting sinogram vector into a 2D matrix of shape (nphi, nrd)
  return torch.reshape(
    torch.mm(sys_mat, torch.reshape(image, (nxd * nxd, 1))),
    (nphi, nrd)
  )

"""**Backward Projection Function**"""

def bp_system_torch(sino, sys_mat, nxd, nrd, nphi):
  return torch.reshape(
    torch.mm(sys_mat.T, torch.reshape(sino, (nrd * nphi, 1))),
    (nxd, nxd)
  ) # Implements the backprojection of the sinogram using the transpose of the system matrix.

# Generate system matrix
sys_mat = make_torch_system_matrix(nxd, nrd, nphi).to(torch.device("cuda:0" if torch.cuda.is_available() else "cpu"))

# Forward projection to compute the sinogram
true_sinogram_torch = fp_system_torch(true_object_torch, sys_mat, nxd, nrd, nphi)

cv2disp('sinogram', torch_to_np(true_sinogram_torch), disp_scale * nxd, 0, disp_scale)

class MLEM_net(torch.nn.Module):
  def __init__(self, sino_for_reconstruction, num_its):
      super(MLEM_net, self).__init__()  # Inherit attributes and methods from nn.Module
      self.num_its = num_its  # Number of iterations to perform
      self.sino_ones = torch.ones_like(sino_for_reconstruction)  # Creates a sinogram filled with ones
      self.sens_image = bp_system_torch(self.sino_ones, sys_mat, nxd, nrd, nphi)  # Compute sensitivity image

  def forward(self, sino_for_reconstruction):
    recon = torch.ones(nxd, nxd).to(device)  # Initialize reconstruction as an image of ones

    for it in range(self.num_its):  # Iterative reconstruction process
      fpsino = fp_system_torch(recon, sys_mat, nxd, nrd, nphi)  # Forward projection of current reconstruction
      ratio = sino_for_reconstruction / (fpsino + 1.0e-9)  # Ratio of measured to projected sinograms
      correction = (
          bp_system_torch(ratio, sys_mat, nxd, nrd, nphi) / (self.sens_image + 1.0e-9)
      )  # Backproject ratio and normalize
      recon = recon * correction  # Update reconstruction by multiplying correction

    # Create a figure with 2x2 subplots for visualization
    fig, axes = plt.subplots(2, 2, figsize=(12, 10))
    print("MLEM Iteration:", it + 1)

    # Display MLEM reconstruction
    axes[0, 0].imshow(torch_to_np(recon), cmap='gray')
    axes[0, 0].set_title("MLEM Reconstruction (Iteration {})".format(it + 1))
    axes[0, 0].axis('off')

    # Display Forward Projection of the reconstruction (FP)
    axes[0, 1].imshow(torch_to_np(fpsino), cmap='gray')
    axes[0, 1].set_title("Forward Projection (FP)")
    axes[0, 1].axis('off')

    # Display the Ratio (measured sinogram / forward projection)
    axes[1, 0].imshow(torch_to_np(ratio), cmap='gray')
    axes[1, 0].set_title("Ratio (Measured/FP)")
    axes[1, 0].axis('off')

    # Display Correction (backprojected ratio)
    axes[1, 1].imshow(torch_to_np(correction), cmap='gray')
    axes[1, 1].set_title("Correction (Backprojected Ratio)")
    axes[1, 1].axis('off')

    # Adjust layout and display the figure
    plt.tight_layout()
    plt.show()

    return recon

import matplotlib.pyplot as plt

# Number of iterations for MLEM reconstruction
core_iterations = 2

# Instantiate the network class -> an object and load onto the GPU
deepnet = MLEM_net(true_sinogram_torch, core_iterations).to(device)

# Perform the reconstruction
mlem_recon = deepnet(true_sinogram_torch)

"""**CNN-MLM**"""

import torch.nn as nn
class CNN(nn.Module):
  def __init__(self):
    super(CNN, self).__init__()
    self.CNN = nn.Sequential(
      nn.Conv2d(1, 8, 7, padding=3),
      nn.PReLU(),
      nn.Conv2d(8, 8, 7, padding=3),
      nn.PReLU(),
      nn.Conv2d(8, 8, 7, padding=3),
      nn.PReLU(),
      nn.Conv2d(8, 8, 7, padding=3),
      nn.PReLU(),
      nn.Conv2d(8, 1, 7, padding=3),
      nn.PReLU(),
    )

  def forward(self, x):
    # Pass the input through the CNN layers
    x = torch.squeeze(self.CNN(x.unsqueeze(0).unsqueeze(0)))
    return x

cnn = CNN().to(device)

class MLEM_CNN_net(nn.Module):
# MLEM Class with CNN Refinement
  def __init__(self, sino_for_reconstruction, num_its, nxd, nrd, nphi, cnn):
    super(MLEM_CNN_net, self).__init__()
    self.num_its = num_its
    self.sino_ones = torch.ones_like(sino_for_reconstruction)
    self.sens_image = bp_system_torch(self.sino_ones, sys_mat, nxd, nrd, nphi)
    self.cnn = cnn

  def forward(self, sino_for_reconstruction):
    recon = torch.ones(nxd, nxd).to(device)

    for it in range(self.num_its):
      fpsino = fp_system_torch(recon, sys_mat, nxd, nrd, nphi)
      ratio = sino_for_reconstruction / (fpsino + 1.0e-9)
      correction = bp_system_torch(ratio, sys_mat, nxd, nrd, nphi) / (self.sens_image + 1.0e-9)
      recon = torch.abs(recon * correction + self.cnn(recon))

    # Create a figure with 2x2 subplots for visualization
    fig, axes = plt.subplots(2, 2, figsize=(12, 10))
    print("MLEM Iteration:", it + 1)

    # Display MLEM reconstruction
    axes[0, 0].imshow(torch_to_np(recon), cmap='gray')
    axes[0, 0].set_title("MLEM Reconstruction (Iteration {})".format(it + 1))
    axes[0, 0].axis('off')

    # Display Forward Projection of the reconstruction (FP)
    axes[0, 1].imshow(torch_to_np(fpsino), cmap='gray')
    axes[0, 1].set_title("Forward Projection (FP)")
    axes[0, 1].axis('off')

    # Display the Ratio (measured sinogram / forward projection)
    axes[1, 0].imshow(torch_to_np(ratio), cmap='gray')
    axes[1, 0].set_title("Ratio (Measured/FP)")
    axes[1, 0].axis('off')

    # Display Correction (backprojected ratio)
    axes[1, 1].imshow(torch_to_np(correction), cmap='gray')
    axes[1, 1].set_title("Correction (Backprojected Ratio)")
    axes[1, 1].axis('off')

    # Adjust layout and display the figure
    plt.tight_layout()
    plt.show()

    return recon

# nxd = 128  # Number of detector pixels (or size of the image)
# nrd = int(nxd * 1.42)  # Number of detector bins (typically proportional to nxd)
# nphi = nxd  # Number of projection angles

cnn_mlem = MLEM_CNN_net(true_sinogram_torch, core_iterations, nxd, nrd, nphi, cnn).to(device)
cnn_mlem_recon = cnn_mlem(true_sinogram_torch)

# Define the Mean Squared Error (MSE) loss function
loss_fun = nn.MSELoss()

# Define the optimizer (Adam optimizer)
optimiser = torch.optim.Adam(cnn_mlem.parameters(), lr=0.001)

# Initialize variables for training
train_loss = []  # List to store the loss for each epoch
epochs = 250  # Number of epochs for training

# Training loop
for ep in range(epochs):
  # Forward pass: get the reconstruction from the model
  rec_out = cnn_mlem(true_sinogram_torch)

  # Compute the loss between the reconstructed and ground truth images
  loss = loss_fun(rec_out, torch.squeeze(true_object_torch))

  # Store the loss value for tracking
  train_loss.append(loss.item())

  # Backpropagation
  loss.backward()

  # Update model parameters using the optimizer
  optimiser.step()

  # Reset gradients to zero for the next iteration
  optimiser.zero_grad()

  # Print the epoch number and corresponding training loss
  print("Epoch %d Training loss = %f" % (ep, train_loss[-1]))

"""**MLEM-Attention-CNN**"""

import torch
import torch.nn as nn
import torch.nn.functional as F

class AttentionMechanism(nn.Module):
  def __init__(self, channels):
    super(AttentionMechanism, self).__init__()
    self.query = nn.Conv2d(channels, channels // 8, kernel_size=1)  # Query projection
    self.key = nn.Conv2d(channels, channels // 8, kernel_size=1)    # Key projection
    self.value = nn.Conv2d(channels, channels, kernel_size=1)      # Value projection
    self.softmax = nn.Softmax(dim=-1)                             # Softmax over the attention map

  def forward(self, x):
    b, c, h, w = x.size()
    query = self.query(x).view(b, -1, h * w).permute(0, 2, 1)  # [B, HW, C//8]
    key = self.key(x).view(b, -1, h * w)                       # [B, C//8, HW]
    attention_map = self.softmax(torch.bmm(query, key))        # [B, HW, HW]
    value = self.value(x).view(b, -1, h * w)                   # [B, C, HW]
    out = torch.bmm(value, attention_map.permute(0, 2, 1))     # [B, C, HW]
    out = out.view(b, c, h, w)                                 # Reshape to [B, C, H, W]
    return out + x  # Residual connection

  class AttentionNet(nn.Module):
  def __init__(self):
    super(AttentionNet, self).__init__()
    self.layers = nn.Sequential(
        nn.Conv2d(1, 8, kernel_size=7, padding=3),
        nn.PReLU(),
        AttentionMechanism(8),  # Attention mechanism after first convolution
        nn.Conv2d(8, 8, kernel_size=7, padding=3),
        nn.PReLU(),
        AttentionMechanism(8),  # Attention mechanism after second convolution
        nn.Conv2d(8, 8, kernel_size=7, padding=3),
        nn.PReLU(),
        nn.Conv2d(8, 8, kernel_size=7, padding=3),
        nn.PReLU(),
        nn.Conv2d(8, 1, kernel_size=7, padding=3),
        nn.PReLU(),
    )

  def forward(self, x):
    # Pass the input through the layers
    x = self.layers(x.unsqueeze(0).unsqueeze(0))  # Add batch and channel dimensions
    x = x.squeeze(0).squeeze(0)  # Remove batch and channel dimensions
    return x

attn_cnn = AttentionNet().to(device)

class MLEM_attn_CNN_net(nn.Module):
# MLEM Class with CNN Refinement
  def __init__(self, sino_for_reconstruction, num_its, nxd, nrd, nphi, cnn):
    super(MLEM_attn_CNN_net, self).__init__()
    self.num_its = num_its
    self.sino_ones = torch.ones_like(sino_for_reconstruction)
    self.sens_image = bp_system_torch(self.sino_ones, sys_mat, nxd, nrd, nphi)
    self.attn_cnn = attn_cnn

  def forward(self, sino_for_reconstruction):
    recon = torch.ones(nxd, nxd).to(device)

    for it in range(self.num_its):
      fpsino = fp_system_torch(recon, sys_mat, nxd, nrd, nphi)
      ratio = sino_for_reconstruction / (fpsino + 1.0e-9)
      correction = bp_system_torch(ratio, sys_mat, nxd, nrd, nphi) / (self.sens_image + 1.0e-9)
      recon = torch.abs(recon * correction + self.attn_cnn(recon))

    # Create a figure with 2x2 subplots for visualization
    fig, axes = plt.subplots(2, 2, figsize=(12, 10))
    print("MLEM Iteration:", it + 1)

    # Display MLEM reconstruction
    axes[0, 0].imshow(torch_to_np(recon), cmap='gray')
    axes[0, 0].set_title("MLEM Reconstruction (Iteration {})".format(it + 1))
    axes[0, 0].axis('off')

    # Display Forward Projection of the reconstruction (FP)
    axes[0, 1].imshow(torch_to_np(fpsino), cmap='gray')
    axes[0, 1].set_title("Forward Projection (FP)")
    axes[0, 1].axis('off')

    # Display the Ratio (measured sinogram / forward projection)
    axes[1, 0].imshow(torch_to_np(ratio), cmap='gray')
    axes[1, 0].set_title("Ratio (Measured/FP)")
    axes[1, 0].axis('off')

    # Display Correction (backprojected ratio)
    axes[1, 1].imshow(torch_to_np(correction), cmap='gray')
    axes[1, 1].set_title("Correction (Backprojected Ratio)")
    axes[1, 1].axis('off')

    # Adjust layout and display the figure
    plt.tight_layout()
    plt.show()

    return recon

attn_cnn_mlem = MLEM_attn_CNN_net(true_sinogram_torch, core_iterations, nxd, nrd, nphi, attn_cnn).to(device)
attn_cnn_mlem_recon = attn_cnn_mlem(true_sinogram_torch)

# Mean Squared Error (MSE) loss function
loss_fun = nn.MSELoss()

# Define the optimizer (Adam optimizer)
optimiser = torch.optim.Adam(attn_cnn_mlem.parameters(), lr=0.001)

# Initialize variables for training
train_loss = []  # List to store the loss for each epoch
epochs = 250  # Number of epochs for training

# Training loop
for ep in range(epochs):
  # Forward pass: get the reconstruction from the model
  rec_out = attn_cnn_mlem(true_sinogram_torch)

  # Compute the loss between the reconstructed and ground truth images
  loss = loss_fun(rec_out, torch.squeeze(true_object_torch))

  # Store the loss value for tracking
  train_loss.append(loss.item())

  # Backpropagation
  loss.backward()

  # Update model parameters using the optimizer
  optimiser.step()

  # Reset gradients to zero for the next iteration
  optimiser.zero_grad()

  # Print the epoch number and corresponding training loss
  print("Epoch %d Training loss = %f" % (ep, train_loss[-1]))
