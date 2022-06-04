from time import time
import cv2
import torch

from util import Mosaic, DrawRectImg, TrackingID
from args import Args

import ml_part as ML
from database import load_face_db
from facenet_pytorch import InceptionResnetV1

from retinaface_utils.utils.model_utils import load_model
from retinaface_utils.models.retinaface import RetinaFace
from retinaface_utils.data.config import cfg_mnet


def init(args):
    # 초기에 불러올 모델을 설정하는 공간입니다.
    model_args = {}

    device = torch.device('cuda:0' if torch.cuda.is_available() else 'cpu')
    model_args['Device'] = device
    if args['DEBUG_MODE']:
        print('Running on device : {}'.format(device))
    
    # Load Detection Model
    model_path = 'retinaface_utils/weights/mobilenet0.25_Final.pth'
    backbone_path = './retinaface_utils/weights/mobilenetV1X0.25_pretrain.tar'
    model_detection = RetinaFace(cfg=cfg_mnet, backbone_path=backbone_path, phase = 'test')
    model_detection = load_model(model_detection, model_path, device)
    model_detection.to(device)
    model_detection.eval()

    model_args['Detection'] = model_detection

    # Load Recognition Models
    resnet = InceptionResnetV1(pretrained='vggface2').eval().to(device)

    model_args['Recognition'] = resnet

    # Load Face DB
    image_path = "../data/test_images"
    db_path = "./database"

    face_db = load_face_db(image_path, db_path,
                            device, args, model_args)

    model_args['Face_db'] = face_db

    return model_args


def ProcessImage(img, args, model_args, known_ids = None):
    process_target = args['PROCESS_TARGET']

    # Object Detection
    bboxes = ML.Detection(img, args, model_args)
    if bboxes is None:
        return img

    # Object Recognition
    face_ids = ML.Recognition(img, bboxes, args, model_args, known_ids)
    # 이번 프레임의 ids 수집
    if known_ids is not None:
        known_ids.get_ids(face_ids, bboxes)
    
    # Mosaic
    img = Mosaic(img, bboxes, face_ids, n=10)

    # 특정인에 bbox와 name을 보여주고 싶으면
    # 임시 카운트
    processed_img = DrawRectImg(img, bboxes, face_ids, known_ids)

    return processed_img


def main(args):
    model_args = init(args)

    # =================== Image =======================
    image_dir = args['IMAGE_DIR']
    if args['PROCESS_TARGET'] == 'Image':
        # Color channel: BGR
        img = cv2.imread(image_dir)
        img = ProcessImage(img, args, model_args)
        cv2.imwrite(args['SAVE_DIR'] + '/output.jpg', img)
        print('image process complete!')
    # =================== Image =======================

    # =================== Video =======================
    elif args['PROCESS_TARGET'] == 'Video':
        video_path = args['VIDEO_DIR']
        known_ids = TrackingID(IoU_thr=.8, IoU_weight=.4)

        start = time()
        fourcc = cv2.VideoWriter_fourcc(*'XVID')
        cap = cv2.VideoCapture(video_path)
        width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
        height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
        fps = round(cap.get(cv2.CAP_PROP_FPS))
        out = cv2.VideoWriter(args['SAVE_DIR'] + '/output.mp4', fourcc, fps, (width, height))
        while True:
            ret, img = cap.read()
            # Color channel: BGR
            if ret:
                img = ProcessImage(img, args, model_args, known_ids)
                out.write(img)
            else:
                break

        cap.release()
        out.release()
        print('done.', time() - start)
    # ====================== Video ===========================


if __name__ == "__main__":
    args = Args().params
    main(args)
