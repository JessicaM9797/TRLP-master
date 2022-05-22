import numpy as np
from scipy.spatial import ConvexHull, convex_hull_plot_2d
import scipy
import math
import copy
import joblib
import os

#本地化差分隐私扰动机制
class Mechanism():
    def __init__(self):
        pass
    
    def perturb(self, cell_true_loc):
        if not self.is_load:
            raise("you should initially load")
        
        self.surrogated = self._surrogate(cell_true_loc)
        cell_true_loc = self.surrogated
        #返回真实位置+噪声
        return cell_true_loc + self.noise_generator()
    
    def inference(self):
        pass
    
    '''def load_from_jbl(self, name):
        data = joblib.load(os.path.join(os.path.dirname(__file__), "..", "data", name + ".jbl"))
        self.weight_mat, self.locations, self.distance_mat = data["weight_mat"], data["locations"], data["distance_mat"]
        self.names = np.array(self.locations)[:,0]
        self.coords = np.zeros((len(self.locations),2))
        for i, coord in enumerate(np.array(self.locations)[:,1]):
            self.coords[i,:] = coord
            
        self.is_load = True'''
    
    def load(self, coords, state_nos):
        self.is_load = True
        #状态坐标转换位置坐标
        self.state2coord = {state_no: coord for state_no, coord in zip(state_nos, coords)}
        
        self.coords = coords
        self.state_nos = state_nos

    def _check_included(self, cell_true_loc):
        return np.any(np.all(cell_true_loc == self.coords, axis=1))# np.any逻辑或，np.all逻辑与

    #生成真实位置的替换位置[详见PIM论文定义3.2]
    def _surrogate(self, cell_true_loc):
        global surrogated_loc
        
        if not self._check_included(cell_true_loc):
            
            surrogated_loc, _ = self._find_nearest_loc(cell_true_loc)
                    
            return surrogated_loc
        
        else:
            return cell_true_loc

    #找到传入位置附近最近的位置点
    def _find_nearest_loc(self, cell_loc):

        global surrogated_loc, state_no
        min_distance = float("inf")
        
        for i, coord in enumerate(self.coords):
            distance = np.linalg.norm(cell_loc - coord) #求范数
            
            #if distance == 0:
            #    continue
            
            if distance < min_distance:
                min_distance = distance
                surrogated_loc = coord
                state_no = self.state_nos[i]
        
        return surrogated_loc, state_no
    
    def _make_sensitivities(self, coords):
        
        sensitivities = []
        
        size = len(coords)
        for i in range(size):
            for j in range(i,size):#将敏感度累加
                sensitivities += self._compute_sensitivity(coords, i, j)
                
        return np.array(sensitivities) #坐标对的集合，如[(2,1),(1,2)]
    
    def _compute_sensitivity(self, coords, i, j):#敏感度就是坐标之间的差值
        return [(coords[i] - coords[j]), (coords[j] - coords[i])]#格式为坐标对,如(2,1)

#拉普拉斯机制（基线算法）
class LaplaceMechanism(Mechanism):
    
  
    def inference(self, prior_dist, perturbed_loc):

        #发布的扰动位置与真实位置差值的l1-范式值
        l1_norms = np.linalg.norm(self.coords - perturbed_loc, ord=1, axis=1)

        alpha = np.exp(-self.epsilon * l1_norms / self.sensitivity) * prior_dist[self.state_nos]
        #后验概率计算[贝叶斯]
        pos_dist = alpha / np.sum(alpha)
        #得到后验概率分布
        post_distribution = np.zeros(len(prior_dist))
        post_distribution[self.state_nos] = pos_dist
        return post_distribution

    #生成分布
    def build_distribution(self, epsilon):
        self.epsilon = epsilon
        
        sensitivities = self._make_sensitivities(self.coords)
        self.sensitivity = self._l1_sensitivity(sensitivities)
        
        def laplace():
            return np.random.laplace(0, self.sensitivity/self.epsilon, 2)#指定噪声size = 2表示产生二维噪声

        
        self.noise_generator =  laplace
        
        
    def _l1_sensitivity(self, sensitivities):
        
        return np.max(np.linalg.norm(sensitivities, ord=1, axis=1))
    
#CPLP算法
class PlanarIsotropicMechanism(Mechanism):
    
    def __init__(self, iso_trans_sample_size=5000):
        super(PlanarIsotropicMechanism, self).__init__()
        
        self.multiplier = 100#倍数
        #总长度200*200=40000
        self.hull_coords = np.array([[i,j] for i in range(-self.multiplier,self.multiplier) for j in range(-self.multiplier,self.multiplier)])


        self.iso_trans_sample_size = iso_trans_sample_size
        
    def inference(self, prior_dist, cell_z):
        
        pos_dist = np.zeros(len(prior_dist))#后验概率分布初始化
        pos_dist[self.state_nos] = 1
        
        if len(self.state_nos) == 1:
            return pos_dist
        
        transformed_z = self._transform(cell_z.reshape(-1,2))[0]
        
        inference_probs = {}
        
        for state_no, transformed_coord in zip(self.state_nos, self.transformed_coords):
            k = self._k_norm((transformed_z - transformed_coord))
            inference_probs[state_no] = np.exp(-self.epsilon * k) * prior_dist[state_no]

        inference_sum = np.sum(list(inference_probs.values()))

        inference_probs = {state_no: prob/inference_sum for state_no, prob in inference_probs.items()}

        for state_no, prob in inference_probs.items():
            pos_dist[state_no] = prob
        
        return pos_dist

    def _transform(self, vertices):
        return np.dot(self.T, vertices.T).T

    # 作为单独的函数调用
    def _make_k_norm(self, vertices):
        
        def k_norm(vec):
            x,y = vec

            n_vertices = len(vertices)#传入向量的个数
            if n_vertices == 2:
                ks = (vec / vertices)
                k = ks[0][0]
                #处理空值
                if np.isnan(k):
                    k = ks[0][1]
                return abs(k)

            a = 0
            k = 0

            for i in range(n_vertices):
                j = i+1
                if j == n_vertices:
                    j = 0
                v1x, v1y = self.vertices[i][0], self.vertices[i][1]
                v2x, v2y = self.vertices[j][0], self.vertices[j][1]

                b = (v2x-(x/y)*v2y)/((x/y)*(v1y-v2y)-v1x+v2x)
                if b>=0 and b<=1 :
                    a = b/y*(v1y-v2y)+v2y/y
                if a > 0:
                    k = 1/a

            return k
        
        return k_norm

    # 用于本类中数据调用
    def _k_norm(self, vec):

        x,y = vec
        
        n_vertices = len(self.transformed_vertices)
        if n_vertices == 2:
            ks = (vec / self.transformed_vertices)
            k = ks[0][0]
            if np.isnan(k):
                k = ks[0][1]
            return abs(k)
        elif n_vertices == 1:
            return 0
        
        a = 0
        k = 0
        
        for i in range(n_vertices):
            j = i+1
            if j == n_vertices:
                j = 0
            v1x, v1y = self.transformed_vertices[i][0], self.transformed_vertices[i][1]
            v2x, v2y = self.transformed_vertices[j][0], self.transformed_vertices[j][1]
            
            b = (v2x-(x/y)*v2y)/((x/y)*(v1y-v2y)-v1x+v2x)
            if b>=0 and b<=1 :
                a = b/y*(v1y-v2y)+v2y/y
            if a > 0:
                k = 1/a

        return k

    #计算凸包敏感度的面积
    def compute_area_of_sensitivity_hull(self):
        area = 0
        #计算敏感度
        sensitivities = self._make_sensitivities(self.coords)
        #计算敏感度的凸包（形式为坐标对数组）
        vertices = self._make_convex_hull(sensitivities)
        
        n_vertices = len(vertices)

        if n_vertices == 1:
            return 0
        elif n_vertices == 2:
            return np.linalg.norm(vertices[0] - vertices[1])
        else:
            for i in range(n_vertices):
                j = 0 if i == n_vertices-1 else i+1

                coord0 = vertices[i]
                coord1 = vertices[j]

                area += (1/2)*np.abs(np.linalg.det(np.array([coord0,coord1])))#np.linalg.det计算方阵行列式

            return area

    def build_distribution(self, epsilon):
        self.epsilon = epsilon
        
        sensitivities = self._make_sensitivities(self.coords)#这里的敏感度就是坐标对集合(数组)
        vertices = self._make_convex_hull(sensitivities)
        self.T, self.T_i = self._compute_isotropic_transformation(vertices)

        transformed_vertices = self._transform(vertices)
        self.k_norm = self._make_k_norm(transformed_vertices)
        
        self.transformed_coords = self._transform(self.coords)
        
        ### For debug
        
        self.sensitivities = sensitivities
        self.transformed_vertices = transformed_vertices
        self.vertices = vertices
        
        
        def k_norm_generator():
            
            sample = self._sample_point_from_body(self.transformed_vertices)[0]
            noise = np.random.gamma(3, 1/self.epsilon, 1)

            z = noise * np.dot(self.T_i, sample.T)

            return z
        
        self.noise_generator = k_norm_generator
    
    def _sample_point_from_boundary(self, vertices, n_sample = 1, total_length=None, segments=None):
        if total_length is None:
            total_length, segments = self._compute_total_length_of_full(vertices)
            
        samples = np.zeros((n_sample, 2))
            
        for i in range(n_sample):

            random_length = np.random.rand() * total_length
            temp_total_length = random_length
            for seg_i, segment in enumerate(segments):
                if temp_total_length - segment < 0:
                    break
                temp_total_length = temp_total_length - segment

            if seg_i == len(segments)-1:
                seg_j = 0
            else:
                seg_j = seg_i+1

            left_vertex = vertices[seg_i]
            right_vertex = vertices[seg_j]
            
            samples[i,:] = left_vertex + (right_vertex - left_vertex) * temp_total_length / segment
        
        return samples
    
    #计算平面各向同性位置
    def _compute_isotropic_transformation(self, vertices):
        
        try:
            
            if np.all(vertices == 0) or len(vertices) == 2:
                raise
                
            samples = self._sample_point_from_body(vertices, n_sample=self.iso_trans_sample_size)
            #从K(G)中采样,对应公式(8)
            T = np.average([np.dot(sample.reshape(2,-1), sample.reshape(2,-1).T) for sample in samples], axis=0)
            T = np.linalg.inv(T)
            T = scipy.linalg.sqrtm(T)
            T_i = np.linalg.inv(T)

        except:
            T = np.array([[1,0],[0,1]])
            T_i = np.array([[1,0],[0,1]])
                
        
        #if np.isnan(T).any():
        #    print("nan")
        #    T = np.array([[1,0],[0,1]])
        #    T_i = np.array([[1,0],[0,1]]) 
            
        return T, T_i
        
        
    def _compute_total_length_of_full(self, vertices):#顶点
        #计算Δf
        segments = []
        total_length = 0
        for i in range(len(vertices)):
            if i == len(vertices)-1:
                j = 0
            else:
                j = i+1
            segment = np.linalg.norm(vertices[i] - vertices[j])
            segments.append(segment)
            total_length += segment
            
        return total_length, segments
        
    #生成凸包
    def _make_convex_hull(self, vertices):
        
        if len(self.coords) <= 2:
            return vertices
        
        else:
            try:
                self.hull = ConvexHull(vertices)
                self.on_line = False
                return vertices[self.hull.vertices]
            
            except:
                #print("Vertices are on linear (>=3)")
                self.on_line = True
                max_distance = -float("inf")
                for i in range(len(vertices)-1):
                    for j in range(i+1, len(vertices)):
                        distance = np.linalg.norm(vertices[i] - vertices[j])#np.linalg.norm：矩阵中元素平方和开根号
                        if distance > max_distance:
                            max_distance = distance# 找最长距离
                            edges = (i,j)#这里得到的i,j就是最长距离对应的两个坐标点
                return np.array([vertices[edges[0]], vertices[edges[1]]])
            
    def _compute_area_of_sensitivity_hull(self):
        area = 0
        
        n_vertices = len(self.vertices)
        
        if n_vertices == 1:
            return area
        
        if self.on_line or n_vertices == 2:
            return np.linalg.norm(self.vertices[0] - self.vertices[1])
        
        for i in range(n_vertices):
            if i == n_vertices:
                j = 0
            else:
                j = i+1
                
            coord0 = self.vertices[i]
            coord1 = self.vertices[j]
            
            area += (1/2)*np.abs(np.linalg.det(np.array([coord0,coord1])))
        
        return area
            
            
    def n_is_in(self, coord):
        diffs = self.coords - coord
        transformed_diffs = self._transform(diffs)
        k_norm_of_diffs = np.array([self._k_norm(diff) for diff in transformed_diffs])
        is_in = k_norm_of_diffs <= 1 + 1e-4
        n_is_in = np.sum(is_in)
        
        return n_is_in
            

    def _sample_point_from_body(self, vertices, n_sample=1):
        
        if len(self.coords) == 1:#父类中load进来的
            return [self.coords[0]]

        x, y = vertices[:,0], vertices[:,1]#x是所有横坐标值，y是所有纵坐标值
        
        left = np.min(x)
        right = np.max(x)
        lower = np.min(y)
        upper = np.max(y)

        coef = self.multiplier / np.max([[right-left], [upper-lower]])

        try:
            hull = scipy.spatial.Delaunay(coef * vertices)
            
            coords = self.hull_coords[hull.find_simplex(self.hull_coords)>=0] / coef

            random_inds = np.random.randint(len(coords), size=n_sample)

            return coords[random_inds]
        except:
            return self._sample_point_from_boundary(vertices, n_sample=n_sample)