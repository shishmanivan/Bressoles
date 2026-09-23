"""Empire language picker. Region contours use the reference map's 1254px grid."""
import pygame
from adaptive_ui import cover_geometry
from start_page import MASTER_BACKGROUND_PATH, MENU_FONT_PATH

MAP_PATH = 'UI/Languages Map.png'
COMPASS_PATH = 'UI/Languages Compass.png'
EMPIRE_NAMES = {'ENG': 'British Empire', 'DE': 'Deutsches Reich', 'RU': 'Российская империя', 'HU': 'Osztrák–Magyar Monarchia'}
MAP_SHIFT_X = 216
# Only render the framed map; the surrounding parchment belongs to the master.
MAP_FRAME = pygame.Rect(584, 18, 912, 896)
# Crimea coastline traced directly in the current artwork's native coordinates.
CRIMEA_OUTLINE = [
    (1364, 615), (1369, 621), (1378, 623), (1383, 631),
    (1387, 632), (1391, 628), (1399, 627), (1403, 624),
    (1409, 625), (1408, 632), (1401, 634), (1395, 635),
    (1388, 639), (1383, 642), (1380, 650), (1373, 653),
    (1364, 653), (1364, 648), (1359, 642), (1348, 641),
    (1352, 636), (1357, 631),
]
# Austria-Hungary follows the displayed artwork in native 1678x937 coordinates.
AUSTRIA_HUNGARY_OUTLINE = [
    (1028,575),(1042,566),(1055,557),(1071,558),(1087,569),(1097,570),
    (1100,577),(1111,575),(1121,580),(1129,575),(1145,576),(1164,569),
    (1185,567),(1198,560),(1208,568),(1221,569),(1230,577),(1234,593),
    (1234,609),(1229,615),(1239,626),(1234,636),(1241,640),(1248,650),
    (1246,660),(1237,663),(1229,659),(1224,665),(1215,663),(1207,669),
    (1193,675),(1189,683),(1178,685),(1168,683),(1160,688),(1151,682),
    (1145,686),(1136,683),(1129,688),(1115,683),(1105,686),(1099,682),
    (1092,684),(1083,682),(1086,698),(1096,703),(1103,716),(1118,729),
    (1126,733),(1125,738),(1115,735),(1105,728),(1096,725),(1087,715),
    (1077,710),(1065,699),(1062,687),(1057,680),(1051,690),(1048,675),
    (1049,665),(1042,661),(1045,656),(1032,652),(1022,658),(1010,669),
    (1002,673),(999,661),(997,655),(1001,649),(990,642),(991,634),
    (1005,638),(1012,633),(1025,634),(1036,623),(1043,620),(1040,613),
    (1050,607),(1040,604),(1029,605),(1034,595),(1030,590),
]
# Traced coastlines and borders; the Russian region includes Finland and Poland.
REGIONS = {
    'HU': [],
    'ENG': [
        [(268,735),(290,721),(318,713),(329,697),(302,690),(293,680),(310,665),(324,652),(329,629),(317,612),(329,587),(320,571),(339,550),(344,530),(357,516),(388,521),(381,539),(365,559),(380,575),(378,599),(386,622),(390,649),(405,673),(420,681),(418,699),(403,712),(405,730),(375,739),(350,729),(328,738),(311,730),(289,739)],
        [(205,667),(213,649),(222,643),(218,626),(228,612),(224,599),(242,591),(254,600),(268,580),(285,591),(289,610),(278,626),(272,649),(259,669),(237,673),(221,666)],
        [(309,557),(315,541),(321,531),(330,510),(340,510),(336,528),(327,540),(325,555)],
    ],
    'DE': [
        [(542, 640), (560, 650), (579, 664), (595, 660), (615, 671),
         (638, 674), (650, 689), (656, 704), (674, 685), (698, 671),
         (715, 670), (724, 652), (744, 645), (755, 631), (775, 620),
         (791, 627), (798, 643), (792, 660), (779, 674), (757, 679),
         (742, 684), (724, 684), (716, 702), (710, 717), (718, 730),
         (720, 747), (736, 758), (739, 775), (721, 779), (708, 770),
         (698, 767), (687, 752), (666, 747), (648, 752), (630, 762),
         (610, 775), (614, 791), (626, 801), (620, 811), (637, 817),
         (627, 833), (611, 840), (608, 851), (587, 850), (575, 844),
         (553, 849), (545, 841), (517, 845), (519, 821), (531, 803),
         (528, 787), (514, 774), (507, 750), (517, 736), (521, 716),
         (532, 710), (533, 684), (527, 674)],
    ],
    'RU': [
        [(784,187),(798,174),(825,172),(849,180),(864,176),(885,191),(913,191),(932,208),(946,242),(964,214),(982,223),(1003,190),(1019,160),(1037,148),(1066,99),(1088,90),(1100,117),(1117,122),(1130,100),(1149,121),(1165,139),(1182,134),(1200,159),(1205,212),(1226,211),(1226,878),(1204,867),(1160,854),(1111,847),(1098,834),(1080,845),(1061,831),(1042,825),(1025,831),(1019,851),(1000,860),(1013,876),(982,893),(963,880),(944,866),(941,844),(927,823),(911,814),(895,799),(883,789),(882,773),(863,766),(844,755),(826,728),(824,704),(809,681),(796,674),(812,661),(809,641),(815,625),(798,619),(787,605),(768,595),(758,573),(759,548),(777,543),(793,551),(809,548),(807,526),(813,506),(796,510),(781,524),(777,508),(797,491),(836,477),(865,463),(877,447),(899,446),(906,431),(900,414),(884,407),(892,389),(882,371),(856,357),(851,336),(839,327),(841,307),(831,288),(834,269),(823,247),(811,231),(798,221)],
        [(770,198),(784,185),(798,220),(811,232),(823,250),(832,273),(830,289),(840,309),(839,330),(850,342),(854,357),(880,370),(893,390),(884,410),(873,416),(875,442),(856,451),(832,453),(811,463),(792,471),(771,475),(754,463),(744,444),(740,421),(745,398),(735,378),(737,355),(748,340),(735,321),(737,309),(755,307),(759,283),(752,261),(751,245),(740,228),(737,214),(750,207),(757,216)],
        [(782,674),(797,675),(810,684),(821,702),(825,729),(838,750),(822,761),(808,755),(789,768),(769,765),(751,774),(734,770),(732,750),(719,747),(716,727),(710,718),(718,701),(725,686),(744,681),(762,677)],
    ],
}


class LanguagesPage:
    def __init__(self, screen, background, font_path, lang_dict=None, current_language='RU'):
        self.screen = screen
        self.lang = lang_dict or {}
        self.current_language = current_language
        self.clock = pygame.time.Clock()
        self.font_path = MENU_FONT_PATH
        self.master = pygame.image.load(MASTER_BACKGROUND_PATH).convert()
        self.art = pygame.image.load(MAP_PATH).convert()
        self.compass = pygame.image.load(COMPASS_PATH).convert_alpha()
        self.hovered = None
        self.focus = None
        self._size = None
        self.masks = {}
        self.overlays = {}
        for code, polygons in REGIONS.items():
            overlay = pygame.Surface(self.art.get_size(), pygame.SRCALPHA)
            for polygon in polygons:
                points = [(round(355 + MAP_SHIFT_X + x * .749), round(y * .742)) for x, y in polygon]
                pygame.draw.polygon(overlay, (47, 29, 12, 90), points)
            if code == 'HU':
                pygame.draw.polygon(overlay, (47, 29, 12, 90), AUSTRIA_HUNGARY_OUTLINE)
            if code == 'RU':
                pygame.draw.polygon(overlay, (47, 29, 12, 90), CRIMEA_OUTLINE)
            self.overlays[code] = overlay
            self.masks[code] = pygame.mask.from_surface(overlay, 1)
        self._layout()

    def _layout(self):
        size = self.screen.get_size()
        if size == self._size:
            return
        self._size = size
        scale = min(size[0] / 1678, size[1] / 1050)
        self.scale = scale
        self.map_rect = pygame.Rect(0, 0, round(1678*scale), round(937*scale))
        self.map_rect.center = (size[0]//2, size[1]//2)
        self.frame_rect = pygame.Rect(
            self.map_rect.x + round(MAP_FRAME.x * self.map_rect.width / 1678),
            self.map_rect.y + round(MAP_FRAME.y * self.map_rect.height / 937),
            round(MAP_FRAME.width * self.map_rect.width / 1678),
            round(MAP_FRAME.height * self.map_rect.height / 937),
        )
        compass_scale = min(230 / self.compass.get_width(), 285 / self.compass.get_height()) * scale
        compass_size = tuple(max(1, round(length * compass_scale)) for length in self.compass.get_size())
        self.scaled_compass = pygame.transform.smoothscale(self.compass, compass_size)
        self.compass_rect = self.scaled_compass.get_rect(center=(
            self.map_rect.left + round(280 * scale),
            self.map_rect.top + round(615 * scale),
        ))
        self.scaled_art = pygame.transform.smoothscale(self.art, self.map_rect.size)
        self.scaled_overlays = {k: pygame.transform.smoothscale(v, self.map_rect.size) for k,v in self.overlays.items()}
        bg_size, self.bg_pos = cover_geometry(self.master.get_size(), size)
        self.scaled_master = pygame.transform.smoothscale(self.master, bg_size)
        self.font = pygame.font.Font(self.font_path, max(16, round(29*scale)))
        self.title_rects = {}
        for index, code in enumerate(EMPIRE_NAMES):
            y = 155 + index * 82
            rect = pygame.Rect(0, 0, round(480*scale), round(62*scale))
            rect.topleft = (self.map_rect.left + round(40*scale), self.map_rect.top + round(y*scale))
            self.title_rects[code] = rect
        self.title_surfaces = {}
        for code, name in EMPIRE_NAMES.items():
            for font_size in range(max(16, round(29 * scale)), 9, -1):
                font = pygame.font.Font(self.font_path, font_size)
                label = font.render(name, True, (57,39,24))
                if label.get_width() <= self.title_rects[code].width - round(24 * scale):
                    break
            self.title_surfaces[code] = label
        self.back_rect = pygame.Rect(self.map_rect.left+round(25*scale), self.map_rect.bottom-round(80*scale), round(270*scale), round(52*scale))

    def region_at(self, pos):
        self._layout()
        for code, rect in self.title_rects.items():
            if rect.collidepoint(pos):
                return code
        if not self.frame_rect.collidepoint(pos):
            return None
        x = int((pos[0]-self.map_rect.x)*1678/self.map_rect.width)
        y = int((pos[1]-self.map_rect.y)*937/self.map_rect.height)
        for code, mask in self.masks.items():
            if mask.get_at((x,y)):
                return code
        return None

    def handle_input(self):
        self._layout()
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                return 'quit'
            if event.type == pygame.VIDEORESIZE:
                self.screen = pygame.display.get_surface() or self.screen
                self._layout()
            if event.type == pygame.MOUSEMOTION:
                self.focus = None
                self.hovered = self.region_at(event.pos)
            if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
                if self.back_rect.collidepoint(event.pos):
                    return 'back'
                code = self.region_at(event.pos)
                if code:
                    return code
            if event.type == pygame.KEYDOWN:
                if event.key == pygame.K_ESCAPE:
                    return 'back'
                if event.key in (pygame.K_TAB, pygame.K_LEFT, pygame.K_RIGHT, pygame.K_UP, pygame.K_DOWN):
                    codes = tuple(EMPIRE_NAMES)
                    direction = -1 if event.key in (pygame.K_LEFT, pygame.K_UP) or (event.key == pygame.K_TAB and getattr(event, 'mod', 0) & pygame.KMOD_SHIFT) else 1
                    index = codes.index(self.focus) if self.focus in codes else (-1 if direction > 0 else 0)
                    self.focus = codes[(index + direction) % len(codes)]
                    self.hovered = self.focus
                if event.key in (pygame.K_RETURN, pygame.K_SPACE) and self.focus:
                    return self.focus
        return None

    def draw(self):
        self._layout()
        self.screen.blit(self.scaled_master, self.bg_pos)
        self.screen.blit(self.scaled_compass, self.compass_rect)
        previous_clip = self.screen.get_clip()
        self.screen.set_clip(previous_clip.clip(self.frame_rect))
        self.screen.blit(self.scaled_art, self.map_rect)
        if self.hovered:
            self.screen.blit(self.scaled_overlays[self.hovered], self.map_rect)
        self.screen.set_clip(previous_clip)
        for code, name in EMPIRE_NAMES.items():
            rect = self.title_rects[code]
            selected = code == self.current_language
            pygame.draw.rect(self.screen, (190,163,118) if selected else (220,197,153), rect, border_radius=5)
            pygame.draw.rect(self.screen, (78,56,34), rect, 3 if self.hovered == code else 1, border_radius=5)
            label = self.title_surfaces[code]
            self.screen.blit(label, label.get_rect(center=rect.center))
        pygame.draw.rect(self.screen, (220,197,153), self.back_rect, border_radius=5)
        label = self.font.render(self.lang.get('SettingsBack','Назад'), True, (57,39,24))
        self.screen.blit(label, label.get_rect(center=self.back_rect.center))
        pygame.display.flip()

    def run(self):
        while True:
            result = self.handle_input()
            if result:
                return result
            self.draw()
            self.clock.tick(60)
