"""Residual network architecture."""

import math

import tensorflow as tf

from ._networks import conv_block
from ._networks import residual_block
from ._networks import upconv_block


def resnet(
    dropout: float = 0.2,
    cell_size: int = 4,
    filters: int = 6,
    n_convs: int = 3,
    conv_after_res: bool = True,
) -> tf.keras.models.Model:
    """Residual network with interspersed dropout.

    Args:
        dropout (float): Percentage of dropout.
        cell_size (int): Size of one cell in the grid.
        filters (int): log2 number of filters in the first convolution layers.
        n_convs (int): number of convolution layers in each convolution block.
        conv_after_res: If True, performs additional convolution block after residual block.
    """
    i = filters  # 2 ** filters represent the number of filters

    if not math.log(cell_size, 2).is_integer():
        raise ValueError(f"cell_size must be a power of 2, but is {cell_size}.")

    inputs = tf.keras.layers.Input(shape=(None, None, 1))
    skip_layers = []

    # Down: halving
    x = conv_block(inputs=inputs, filters=2 ** (i), n_convs=n_convs, dropout=dropout)
    x = residual_block(inputs=x, filters=2 ** (i))
    if conv_after_res:
        x = conv_block(inputs=x, filters=2 ** (i + 1), n_convs=n_convs, dropout=dropout)
        x = tf.keras.layers.Dropout(dropout)(x)
    skip_layers.append(x)
    x = tf.keras.layers.MaxPool2D(pool_size=(2, 2))(x)

    # Down: halving
    x = conv_block(inputs=x, filters=2 ** (i + 1), n_convs=n_convs, dropout=dropout)
    x = residual_block(inputs=x, filters=2 ** (i + 1))
    if conv_after_res:
        x = conv_block(inputs=x, filters=2 ** (i + 1), n_convs=n_convs, dropout=dropout)
        x = tf.keras.layers.Dropout(dropout)(x)
    skip_layers.append(x)
    x = tf.keras.layers.MaxPool2D(pool_size=(2, 2))(x)

    # Dynamic down sampling: if cell_size is higher than 4, to get the correct network output shape,
    # we need to further down-sample by math.log(cell_size, 2) - 2 times.
    # The -2 corresponds to the 2 halvings already done
    ndown = max(0, math.log(cell_size, 2) - 2)
    for n in range(int(ndown)):
        x = conv_block(
            inputs=x, filters=2 ** (i + 1 + n), n_convs=n_convs, dropout=dropout
        )
        x = residual_block(inputs=x, filters=2 ** (i + 1 + n))
        if conv_after_res:
            x = conv_block(
                inputs=x, filters=2 ** (i + 1 + n), n_convs=n_convs, dropout=dropout
            )
            x = tf.keras.layers.Dropout(dropout)(x)
        skip_layers.append(x)
        x = tf.keras.layers.MaxPool2D(pool_size=(2, 2))(x)

    # Dynamic upsampling: if cell_size is smaller than 4, after the 2 halvings,
    # we need to upsample int(2 // cell_size) times
    # If cell_size is 1, we need to upsample 2 == int(2 // cell_size)
    # If cell_size is 2, we need to upsample 1 == int(2 // 2)
    for n in range(int(2 // cell_size)):
        x = conv_block(
            inputs=x, filters=2 ** (i + 1 - n), n_convs=n_convs, dropout=dropout
        )
        x = residual_block(inputs=x, filters=2 ** (i + 1 - n))
        if conv_after_res:
            x = conv_block(
                inputs=x, filters=2 ** (i + 1 - n), n_convs=n_convs, dropout=dropout
            )
            x = tf.keras.layers.Dropout(dropout)(x)
        x = upconv_block(
            inputs=x, skip=skip_layers[-(n + 1)], filters=2 ** (i + 1), n_convs=1
        )

    # Connected
    x = conv_block(inputs=x, filters=2 ** (i + 2), n_convs=n_convs, dropout=dropout)
    x = residual_block(inputs=x, filters=2 ** (i + 2))
    x = conv_block(inputs=x, filters=2 ** (i + 1), n_convs=n_convs, dropout=dropout)
    x = tf.keras.layers.Dropout(dropout)(x)

    # Logit
    x = tf.keras.layers.Conv2D(filters=3, kernel_size=1, strides=1)(x)
    x = tf.keras.layers.Activation("sigmoid")(x)

    return tf.keras.Model(inputs=inputs, outputs=x)
