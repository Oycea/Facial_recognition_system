from dlib import get_frontal_face_detector

detector = get_frontal_face_detector()


def face_detector(screen):
    faces = detector(screen)

    faces_list = []
    for face in faces:
        left_x, left_y = face.left(), face.top()
        right_x, right_y = face.right(), face.bottom()

        faces_list.append(screen[left_y:right_y, left_x:right_x])

    return faces_list
