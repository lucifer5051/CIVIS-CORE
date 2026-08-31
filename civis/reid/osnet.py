"""
OSNet: Omni-Scale Feature Learning for Person Re-Identification
Adapted from KaiyangZhou/deep-person-reid (MIT License)

Reference:
    Zhou et al. Omni-Scale Feature Learning for Person Re-Identification. ICCV 2019.
    https://github.com/KaiyangZhou/deep-person-reid
"""

import torch
from torch import nn
from torch.nn import functional as F


class ConvLayer(nn.Module):
    def __init__(
        self,
        in_channels: int,
        out_channels: int,
        kernel_size: int,
        stride: int = 1,
        padding: int = 0,
        groups: int = 1,
        IN: bool = False,
    ) -> None:
        super().__init__()
        self.conv = nn.Conv2d(
            in_channels,
            out_channels,
            kernel_size,
            stride=stride,
            padding=padding,
            bias=False,
            groups=groups,
        )
        if IN:
            self.bn = nn.InstanceNorm2d(out_channels, affine=True)
        else:
            self.bn = nn.BatchNorm2d(out_channels)
        self.relu = nn.ReLU(inplace=True)

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        return self.relu(self.bn(self.conv(x)))


class Conv1x1(nn.Module):
    def __init__(self, in_channels: int, out_channels: int, stride: int = 1, groups: int = 1, IN: bool = False) -> None:
        super().__init__()
        self.conv = nn.Conv2d(
            in_channels,
            out_channels,
            1,
            stride=stride,
            padding=0,
            bias=False,
            groups=groups,
        )
        if IN:
            self.bn = nn.InstanceNorm2d(out_channels, affine=True)
        else:
            self.bn = nn.BatchNorm2d(out_channels)
        self.relu = nn.ReLU(inplace=True)

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        return self.relu(self.bn(self.conv(x)))


class LightConv3x3(nn.Module):
    """
    Lightweight 3x3 convolution composed of 1x1 linear conv and 3x3 depthwise conv.
    """
    def __init__(self, in_channels: int, out_channels: int) -> None:
        super().__init__()
        self.conv1 = nn.Conv2d(in_channels, out_channels, 1, bias=False)
        self.conv2 = nn.Conv2d(out_channels, out_channels, 3, padding=1, bias=False, groups=out_channels)
        self.bn = nn.BatchNorm2d(out_channels)
        self.relu = nn.ReLU(inplace=True)

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        x = self.conv1(x)
        x = self.conv2(x)
        x = self.bn(x)
        return self.relu(x)


class ChannelGate(nn.Module):
    """A mini-network that generates channel-wise attention weights."""
    def __init__(self, in_channels: int, num_gates: int = None, return_gates: bool = False, gate_activation: str = "sigmoid") -> None:
        super().__init__()
        if num_gates is None:
            num_gates = in_channels
        self.return_gates = return_gates
        self.global_avgpool = nn.AdaptiveAvgPool2d(1)
        self.fc1 = nn.Conv2d(in_channels, in_channels // 16, 1, bias=True)
        self.relu6 = nn.ReLU6(inplace=True)
        self.fc2 = nn.Conv2d(in_channels // 16, num_gates, 1, bias=True)
        if gate_activation == "sigmoid":
            self.gate_activation = nn.Sigmoid()
        elif gate_activation == "relu":
            self.gate_activation = nn.ReLU(inplace=True)
        else:
            raise ValueError(f"Unknown gate activation: {gate_activation}")

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        input_tensor = x
        x = self.global_avgpool(x)
        x = self.fc1(x)
        x = self.relu6(x)
        x = self.fc2(x)
        if self.gate_activation:
            x = self.gate_activation(x)
        if self.return_gates:
            return x
        return input_tensor * x


class OSBlock(nn.Module):
    """Omni-scale feature learning block."""
    def __init__(self, in_channels: int, out_channels: int, IN: bool = False, bottleneck_reduction: int = 4) -> None:
        super().__init__()
        mid_channels = out_channels // bottleneck_reduction
        self.conv1 = Conv1x1(in_channels, mid_channels, IN=IN)
        self.conv2a = LightConv3x3(mid_channels, mid_channels)
        self.conv2b = nn.Sequential(
            LightConv3x3(mid_channels, mid_channels),
            LightConv3x3(mid_channels, mid_channels),
        )
        self.conv2c = nn.Sequential(
            LightConv3x3(mid_channels, mid_channels),
            LightConv3x3(mid_channels, mid_channels),
            LightConv3x3(mid_channels, mid_channels),
        )
        self.conv2d = nn.Sequential(
            LightConv3x3(mid_channels, mid_channels),
            LightConv3x3(mid_channels, mid_channels),
            LightConv3x3(mid_channels, mid_channels),
            LightConv3x3(mid_channels, mid_channels),
        )
        self.gate = ChannelGate(mid_channels)
        self.conv3 = Conv1x1(mid_channels, out_channels, IN=IN)

        self.downsample = None
        if in_channels != out_channels:
            self.downsample = Conv1x1(in_channels, out_channels, IN=IN)

        self.relu = nn.ReLU(inplace=True)

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        residual = x if self.downsample is None else self.downsample(x)
        x1 = self.conv1(x)
        x2a = self.conv2a(x1)
        x2b = self.conv2b(x1)
        x2c = self.conv2c(x1)
        x2d = self.conv2d(x1)
        x2 = self.gate(x2a + x2b + x2c + x2d)
        x3 = self.conv3(x2)
        out = self.relu(x3 + residual)
        return out


class OSNet(nn.Module):
    """
    Omni-Scale Network (OSNet) for Person Re-Identification.
    Produces 512-d L2-normalized appearance embeddings.
    """
    def __init__(
        self,
        num_classes: int = 1000,
        blocks: list = [2, 2, 2],
        layers: list = [64, 256, 384, 512],
        channels: list = [64, 256, 384, 512],
        feature_dim: int = 512,
        IN: bool = False,
    ) -> None:
        super().__init__()
        num_blocks = len(blocks)
        assert num_blocks == 3

        self.conv1 = ConvLayer(3, channels[0], 7, stride=2, padding=3, IN=IN)
        self.maxpool = nn.MaxPool2d(3, stride=2, padding=1)

        self.conv2 = self._make_layer(
            OSBlock, blocks[0], channels[0], channels[1], reduce_spatial_size=True, IN=IN
        )
        self.conv3 = self._make_layer(
            OSBlock, blocks[1], channels[1], channels[2], reduce_spatial_size=True, IN=IN
        )
        self.conv4 = self._make_layer(
            OSBlock, blocks[2], channels[2], channels[3], reduce_spatial_size=False, IN=IN
        )

        self.conv5 = Conv1x1(channels[3], channels[3], IN=IN)
        self.global_avgpool = nn.AdaptiveAvgPool2d(1)
        self.fc = nn.Sequential(
            nn.Linear(channels[3], feature_dim),
            nn.BatchNorm1d(feature_dim),
            nn.ReLU(inplace=True),
        )

    def _make_layer(
        self,
        block: nn.Module,
        layer_count: int,
        in_channels: int,
        out_channels: int,
        reduce_spatial_size: bool,
        IN: bool = False,
    ) -> nn.Sequential:
        layers = []
        layers.append(block(in_channels, out_channels, IN=IN))
        for _ in range(1, layer_count):
            layers.append(block(out_channels, out_channels, IN=IN))
        if reduce_spatial_size:
            layers.append(
                nn.Sequential(
                    Conv1x1(out_channels, out_channels, IN=IN),
                    nn.AvgPool2d(2, stride=2),
                )
            )
        return nn.Sequential(*layers)

    def forward(self, x: torch.Tensor, normalize: bool = True) -> torch.Tensor:
        """
        Forward pass.
        Args:
            x: Tensor of shape (B, 3, 256, 128)
            normalize: Whether to apply L2 normalization to output embeddings
        Returns:
            Tensor of shape (B, 512)
        """
        x = self.maxpool(self.conv1(x))
        x = self.conv2(x)
        x = self.conv3(x)
        x = self.conv4(x)
        x = self.conv5(x)
        v = self.global_avgpool(x)
        v = v.view(v.size(0), -1)
        feat = self.fc(v)
        if normalize:
            feat = F.normalize(feat, p=2, dim=1)
        return feat


def build_osnet_x1_0(pretrained: bool = False, weights_path: str = None) -> OSNet:
    """Builds OSNet-x1.0 instance."""
    model = OSNet(blocks=[2, 2, 2], layers=[64, 256, 384, 512], channels=[64, 256, 384, 512], feature_dim=512)
    if weights_path and torch.cuda.is_available():
        state_dict = torch.load(weights_path, map_location="cuda")
        model.load_state_dict(state_dict, strict=False)
    elif weights_path:
        state_dict = torch.load(weights_path, map_location="cpu")
        model.load_state_dict(state_dict, strict=False)
    return model
