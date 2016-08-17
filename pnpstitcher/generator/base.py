from abc import ABCMeta
from collections import namedtuple


CutLine = namedtuple('CutLine', ['x0', 'y0', 'x1', 'y1'])


class BaseGenerator(object):
    __metaclass__ = ABCMeta

    def __init__(
            self, filename, page_width, page_height, page_margin_x=0,
            page_margin_y=0, image_dpi=300, page_dpi=96):
        """
        :param str filename: The filename of the output PDF file.
        :param int page_width: Page width in inches.
        :param int page_height: Page height in inches.
        :param int page_margin_x: The paper margin on the x-axis in inches
                                  (both sides).
        :param int page_margin_y: The paper margin on the y-axis in inches
                                  (both sides).
        :param int image_dpi: The image dpi.
        :param int page_dpi: The page dpi.
        """
        self.filename = filename
        self.page_width = page_width
        self.page_height = page_height
        self.page_margin_x = page_margin_x
        self.page_margin_y = page_margin_y
        self.image_dpi = image_dpi
        self.page_dpi = page_dpi
        self.image_scale = self.page_dpi / self.image_dpi

    def generate(self, image_catalog, cutline_config, rtl=False):
        """
        Generate the output file.

        :param ImageCatalog image_catalog: The loaded image database.
        :param dict cutline_config: The cutline configuration.
        :param bool rtl: Layout the images from right-to-left.
        """
        self._generate_cut_line(
            image_catalog.image_size,
            (cutline_config['trim_offset_x'], cutline_config['trim_offset_y']))

        # Start the rendering
        image_width = image_catalog.image_size[0] / self.image_dpi
        image_height = image_catalog.image_size[1] / self.image_dpi
        x_cnt = 0
        y_cnt = 0
        x_pos = 0
        y_pos = 0

        for pil_image in image_catalog.image_set:
            # Draw cut lines if it's a fresh page
            if x_cnt == 0 and y_cnt == 0:
                self._initialize_page()
                if cutline_config['layer'] == 'bottom':
                    self._draw_cutlines(cutline_config)

            # Draw the image
            if rtl:
                x_pos = (
                    self.page_width - self._cut_margin_x -
                    ((x_cnt + 1) * image_width))
            else:
                x_pos = self._cut_margin_x + (x_cnt * image_width)
            y_pos = self._cut_margin_y + (y_cnt * image_height)
            self._draw_image(
                pil_image, x_pos, y_pos, (image_width, image_height))

            # Switch to next row when it is happening
            x_cnt = x_cnt + 1
            if x_cnt >= self._card_num_x:
                x_cnt = 0
                y_cnt = y_cnt + 1

            # If we got past the page threshold, we would need to cease it
            if y_cnt >= self._card_num_y:
                x_cnt = 0
                y_cnt = 0
                if cutline_config['layer'] == 'top':
                    self._draw_cutlines(cutline_config)
                self._render_page()

        # After we hit the last page and if there's some left-over that is not
        # rendered, we should do it now.
        if x_cnt != 0 or y_cnt != 0:
            if cutline_config['layer'] == 'top':
                self._draw_cutlines(cutline_config)
            self._render_page()

    def _initialize_page(self):
        """
        Start a fresh page.
        """
        raise NotImplemented()

    def _render_page(self):
        """
        Render page.
        """
        raise NotImplemented()

    def _draw_image(self, image, x_pos, y_pos, image_dimension):
        """
        Draw image onto page.

        :param Image image: The image.
        :param int x_pos: The x position in inches.
        :param int y_pos: The y position in inches.
        :param list image_dimension: A 2-tuple containing the image width and
            height.
        """
        raise NotImplemented()

    def _draw_cutlines(self, cutline_config):
        """
        Draw cutlines.

        :param dict cutline_config: The cutline configuration.
        """
        raise NotImplemented()

    def _generate_cut_line(self, image_dimension, trim_offset=(0, 0)):
        """
        Generate the page frame meta.

        :param tuple image_dimension: A 2-tuple containing the width and height
            of the card images in inches.
        :param int trim_offset: The trim offset in inches in a (x, y) list.
        :returns: The metadata of the page.
        """
        image_width = image_dimension[0] / self.image_dpi
        image_height = image_dimension[1] / self.image_dpi
        trim_x, trim_y = trim_offset
        self._card_num_x, self._cut_margin_x = divmod(
            round(self.page_width - self.page_margin_x * 2), image_width)
        self._card_num_y, self._cut_margin_y = divmod(
            round(self.page_height - self.page_margin_y * 2), image_height)
        self._card_num_x = int(self._card_num_x)
        self._card_num_y = int(self._card_num_y)
        self._cut_margin_x = self._cut_margin_x / 2 + self.page_margin_x
        self._cut_margin_y = self._cut_margin_y / 2 + self.page_margin_y

        if self._card_num_x == 0 or self._card_num_y == 0:
            raise RuntimeError('Image too large for the page')

        # Generate the vertical cutlines
        cutline_set = []
        prev_x = self._cut_margin_x
        if not trim_x:
            # If it's a clean cut, we need to draw the left-most cut line
            cutline_set.append(CutLine(prev_x, 0, prev_x, self.page_height))

        for cnt in range(self._card_num_x):
            next_x = prev_x + image_width
            if trim_x:
                left_cut = prev_x + trim_x
                right_cut = next_x - trim_x
                cutline_set.append(CutLine(
                    left_cut, 0, left_cut, self.page_height))
                cutline_set.append(CutLine(
                    right_cut, 0, right_cut, self.page_height))
            else:
                cutline_set.append(CutLine(
                    next_x, 0, next_x, self.page_height))

            prev_x = next_x

        # Generate the horizontal cutlines
        prev_y = self._cut_margin_y
        if not trim_y:
            # If it's a clean cut, we need to draw the top-most cut line
            cutline_set.append(CutLine(0, prev_y, self.page_width, prev_y))

        for cnt in range(self._card_num_y):
            next_y = prev_y + image_height
            if trim_y:
                top_cut = prev_y + trim_y
                bottom_cut = next_y - trim_y
                cutline_set.append(CutLine(
                    0, top_cut, self.page_width, top_cut))
                cutline_set.append(CutLine(
                    0, bottom_cut, self.page_width, bottom_cut))
            else:
                cutline_set.append(CutLine(0, next_y, self.page_width, next_y))

            prev_y = next_y

        self._cutline_set = cutline_set
