import json
import numpy as np
import math

from flightsim.shapes import Cuboid
from flightsim.numpy_encoding import NumpyJSONEncoder, to_ndarray
# from timeout import timeout
import time
import sys
import traceback


def interp_path(path, res):
    cumdist = np.cumsum(np.linalg.norm(np.diff(path, axis=0),axis=1))
    if cumdist[-1] > 0:
        t = np.insert(cumdist,0,0)
        ts = np.arange(0, cumdist[-1], res)
        pts = np.empty((ts.size, 3), dtype=np.float)
        for k in range(3):
            pts[:,k] = np.interp(ts, t, path[:,k])
    else:
        pts = path[[0],:]
    return pts

class World(object):

    def __init__(self, world_data):
        """
        Construct World object from data. Instead of using this constructor
        directly, see also class methods 'World.from_file()' for building a
        world from a saved .json file or 'World.grid_forest()' for building a
        world object of a parameterized style.

        Parameters:
            world_data, dict containing keys 'bounds' and 'blocks'
                bounds, dict containing key 'extents'
                    extents, list of [xmin, xmax, ymin, ymax, zmin, zmax]
                blocks, list of dicts containing keys 'extents' and 'color'
                    extents, list of [xmin, xmax, ymin, ymax, zmin, zmax]
                    color, color specification
        """
        self.world = world_data

    @classmethod
    def from_file(cls, filename):
        """
        Read world definition from a .json text file and return World object.

        Parameters:
            filename

        Returns:
            world, World object

        Example use:
            my_world = World.from_file('my_filename.json')
        """
        with open(filename) as file:
            return cls(to_ndarray(json.load(file)))

    def to_file(self, filename):
        """
        Write world definition to a .json text file.

        Parameters:
            filename

        Example use:
            my_word.to_file('my_filename.json')
        """
        with open(filename, 'w') as file:  # TODO check for directory to exist
            file.write(json.dumps(self.world, cls=NumpyJSONEncoder, indent=4))

    def closest_points(self, points):
        """
        For each point, return the closest occupied point in the world and the
        distance to that point. This is appropriate for computing sphere-vs-world
        collisions.

        Input
            points, (N,3)
        Returns
            closest_points, (N,3)
            closest_distances, (N,)
        """

        closest_points = np.empty_like(points)
        closest_distances = np.full(points.shape[0], np.inf)
        p = np.empty_like(points)
        for block in self.world.get('blocks', []):
            # Computation takes advantage of axes-aligned blocks. Note that
            # scipy.spatial.Rectangle can compute this distance, but wouldn't
            # return the point itself.
            r = block['extents']
            for i in range(3):
                p[:, i] = np.clip(points[:, i], r[2*i], r[2*i+1])
            d = np.linalg.norm(points-p, axis=1)
            mask = d < closest_distances
            closest_points[mask, :] = p[mask, :]
            closest_distances[mask] = d[mask]
        return (closest_points, closest_distances)

    def path_collisions(self, path, margin):
        """
        Densely sample the path and check for collisions. Return a boolean mask
        over the samples and the sample points themselves.
        """
        pts = interp_path(path, res=0.001)
        (closest_pts, closest_dist) = self.closest_points(pts)
        collisions = closest_dist < margin
        return pts[collisions]

    def draw_empty_world(self, ax):
        """
        Draw just the world without any obstacles yet. The boundary is represented with a black line.
        Parameters:
            ax, Axes3D object
        """
        (xmin, xmax, ymin, ymax, zmin, zmax) = self.world['bounds']['extents']

        # Set axes limits all equal to approximate 'axis equal' display.
        x_width = xmax-xmin
        y_width = ymax-ymin
        z_width = zmax-zmin
        width = np.max((x_width, y_width, z_width))
        ax.set_xlim((xmin, xmin+width))
        ax.set_ylim((ymin, ymin+width))
        ax.set_zlim((zmin, zmin+width))
        ax.set_xlabel('x')
        ax.set_ylabel('y')
        ax.set_zlabel('z')
        c = Cuboid(ax, xmax-xmin, ymax-ymin, zmax-zmin, alpha=0.01, linewidth=1, edgecolors='k')
        c.transform(position=(xmin, ymin, zmin))
        return list(c.artists)

    def draw(self, ax):
        """
        Draw world onto existing Axes3D axes and return artists corresponding to the
        blocks.

        Parameters:
            ax, Axes3D object

        Returns:
            block_artists, list of Artists associated with blocks

        Example use:
            my_world.draw(ax)
        """

        bounds_artists = self.draw_empty_world(ax)
        block_artists = []


        for b in self.world.get('blocks', []):
            (xmin, xmax, ymin, ymax, zmin, zmax) = b['extents']
            c = Cuboid(ax, xmax-xmin, ymax-ymin, zmax-zmin, alpha=0.6, linewidth=1, edgecolors='k', facecolors=b.get('color', None))
            c.transform(position=(xmin, ymin, zmin))
            block_artists.extend(c.artists)
        return bounds_artists + block_artists

    def draw_line(self, ax, points, color=None, linewidth=2):
        path_length = np.sum(np.linalg.norm(np.diff(points, axis=0),axis=1))
        pts = interp_path(points, res=path_length/1000)
        # The scatter object is assigned a single z-order value. Split for better occlusion rendering.
        for p in np.array_split(pts, 20):
            ax.scatter(p[:,0], p[:,1], p[:,2], s=linewidth**2, c=color, edgecolors='none', depthshade=False)

    def draw_points(self, ax, points, color=None, markersize=4):
        # The scatter object is assigned a single z-order value. Split for better occlusion rendering.
        for p in np.array_split(points, 20):
            ax.scatter(p[:,0], p[:,1], p[:,2], s=markersize**2, c=color, edgecolors='none', depthshade=False)

    # The follow class methods are convenience functions for building different
    # kinds of parametric worlds.

    @classmethod
    def empty(cls, extents):
        """
        Return World object for bounded empty space.

        Parameters:
            extents, tuple of (xmin, xmax, ymin, ymax, zmin, zmax)

        Returns:
            world, World object

        Example use:
            my_world = World.empty((xmin, xmax, ymin, ymax, zmin, zmax))
        """
        bounds = {'extents': extents}
        blocks = []
        world_data = {'bounds': bounds, 'blocks': blocks}
        return cls(world_data)

    @classmethod
    def grid_forest(cls, n_rows, n_cols, width, height, spacing):
        """
        Return World object describing a grid forest world parameterized by
        arguments. The boundary extents fit tightly to the included trees.

        Parameters:
            n_rows, rows of trees stacked in the y-direction
            n_cols, columns of trees stacked in the x-direction
            width, weight of square cross section trees
            height, height of trees
            spacing, spacing between centers of rows and columns

        Returns:
            world, World object

        Example use:
            my_world = World.grid_forest(n_rows=4, n_cols=3, width=0.5, height=3.0, spacing=2.0)
        """

        # Bounds are outer boundary for world, which are an implicit obstacle.
        x_max = (n_cols-1)*spacing + width
        y_max = (n_rows-1)*spacing + width
        bounds = {'extents': [0, x_max, 0, y_max, 0, height]}

        # Blocks are obstacles in the environment.
        x_root = spacing * np.arange(n_cols)
        y_root = spacing * np.arange(n_rows)
        blocks = []
        for x in x_root:
            for y in y_root:
                blocks.append({'extents': [x, x+width, y, y+width, 0, height], 'color': [1, 0, 0]})

        world_data = {'bounds': bounds, 'blocks': blocks}
        return cls(world_data)

    @classmethod
    def random_forest(cls, world_dims, tree_width, tree_height, num_trees):
        """
        Return World object describing a random forest world parameterized by
        arguments.

        Parameters:
            world_dims, a tuple of (xmax, ymax, zmax). xmin,ymin, and zmin are set to 0.
            tree_width, weight of square cross section trees
            tree_height, height of trees
            num_trees, number of trees

        Returns:
            world, World object
        """

        # Bounds are outer boundary for world, which are an implicit obstacle.
        bounds = {'extents': [0, world_dims[0], 0, world_dims[1], 0, world_dims[2]]}

        # Blocks are obstacles in the environment.
        xs = np.random.uniform(0, world_dims[0], num_trees)
        ys = np.random.uniform(0, world_dims[1], num_trees)
        pts = np.stack((xs, ys), axis=-1) # min corner location of trees
        w, h = tree_width, tree_height
        blocks = []
        for pt in pts:
            extents = list(np.round([pt[0], pt[0]+w, pt[1], pt[1]+w, 0, h], 2))
            blocks.append({'extents': extents, 'color': [1, 0, 0]})

        world_data = {'bounds': bounds, 'blocks': blocks}
        return cls(world_data)


    @classmethod
    def random_block(cls, lower_bounds,upper_bounds,block_width, block_height, num_blocks,robot_radii,margin):
        """
                Return World object describing a random forest block parameterized by
                arguments.

                Parameters:
                    upper_bounds, a tuple of (xmin,ymin, zmin)  world boundary
                    lower_bounds, a tuple of (xmax, ymax, zmax)
                    block_width, weight of square cross section trees
                    block_height, height of trees
                    num_blocks, number of blocks
                    robot_radius,margin

                Returns:
                    world, World object
                """
        # Bounds are outer boundary for world, which are an implicit obstacle.
        bounds = {'extents': [lower_bounds[0], upper_bounds[0], lower_bounds[1], upper_bounds[1], lower_bounds[2], upper_bounds[2]]}

        # Blocks are obstacles in the environment.
        w, h = block_width, block_height
        xs = np.random.uniform(lower_bounds[0]+w/2, upper_bounds[0]-w/2)
        ys = np.random.uniform(lower_bounds[1]+w/2, upper_bounds[1]-w/2)
        zs = np.random.uniform(lower_bounds[2]+h/2, upper_bounds[2]-h/2)
        pt=np.array([xs,ys,zs])
        blocks = []
        extents = list(np.round([pt[0] - w / 2, pt[0] + w / 2, pt[1] - w / 2, pt[1] + w / 2, pt[2] - h / 2, pt[2] + h / 2], 2))
        blocks.append({'extents': extents, 'color': [1, 0, 0]})

        if num_blocks>1:
            numb = 1
            while True:
                while True:
                    flag=0
                    xs = np.random.uniform(lower_bounds[0] + w / 2, upper_bounds[0] - w / 2)
                    ys = np.random.uniform(lower_bounds[1] + w / 2, upper_bounds[1] - w / 2)
                    zs = np.random.uniform(lower_bounds[2] + h / 2, upper_bounds[2] - h / 2)
                    pt = np.array([xs, ys, zs])
                    k=0
                    while True:
                        if np.linalg.norm(
                                np.array([blocks[k]['extents'][0] + w / 2, blocks[k]['extents'][2] + w / 2,
                                          blocks[k]['extents'][4] + h / 2])
                                - np.array([pt[0], pt[1], pt[2]])
                        ) < 2 * math.sqrt(2 * w ** 2) + 2 * robot_radii + 2 * margin:
                            flag=1
                            break
                        else:
                            k+=1
                        if k>=len(blocks):
                            break

                    if flag==1:
                        continue
                    elif flag==0:
                        extents = list(np.round([pt[0] - w / 2, pt[0] + w / 2, pt[1] - w / 2, pt[1] + w / 2, pt[2] - h / 2, pt[2] + h / 2], 2))
                        blocks.append({'extents': extents, 'color': [1, 0, 0]})
                        numb += 1
                        break


                if numb>=num_blocks:
                    break
                else:
                    continue
        
        
        #Start  position
        while True:
            xs1 = np.random.uniform(lower_bounds[0] + (robot_radii+margin), upper_bounds[0] - (robot_radii+margin))
            ys1 = np.random.uniform(lower_bounds[1] + (robot_radii+margin), upper_bounds[1] - (robot_radii+margin))
            zs1 = np.random.uniform(lower_bounds[2] + (robot_radii+margin), upper_bounds[2] - (robot_radii+margin))
            pt1 = np.array([xs1, ys1, zs1]).reshape(1,-1)

            closest_points = np.empty_like(pt1)
            closest_distances = np.full(pt1.shape[0], np.inf)

            p = np.empty_like(pt1)
            for block in blocks:
                r = block['extents']
                for i in range(3):
                    p[:, i] = np.clip(pt1[:, i], r[2 * i], r[2 * i + 1])
                d = np.linalg.norm(pt1 - p, axis=1)
                mask = d < closest_distances
                closest_points[mask, :] = p[mask, :]
                closest_distances[mask] = d[mask]
            if closest_distances[0]>robot_radii+margin:
                start = np.array([pt1[0][0], pt1[0][1], pt1[0][2]])
                # print(closest_points, closest_distances)
                break

            else:
                continue
        #Goal position
        while True:
            xs2 = np.random.uniform(lower_bounds[0] + (robot_radii + margin),
                                    upper_bounds[0] - (robot_radii + margin))
            ys2 = np.random.uniform(lower_bounds[1] + (robot_radii + margin),
                                    upper_bounds[1] - (robot_radii + margin))
            zs2 = np.random.uniform(lower_bounds[2] + (robot_radii + margin),
                                    upper_bounds[2] - (robot_radii+ margin))
            pt2 = np.array([xs2, ys2, zs2]).reshape(1, -1)

            closest_points = np.empty_like(pt2)
            closest_distances = np.full(pt2.shape[0], np.inf)

            p = np.empty_like(pt2)
            for block in blocks:
                r = block['extents']
                for i in range(3):
                    p[:, i] = np.clip(pt2[:, i], r[2 * i], r[2 * i + 1])
                d = np.linalg.norm(pt2 - p, axis=1)
                mask = d < closest_distances
                closest_points[mask, :] = p[mask, :]
                closest_distances[mask] = d[mask]
            if closest_distances[0] > robot_radii + margin and np.linalg.norm(np.array([start[0],start[1],start[2]])-np.array([pt2[0][0], pt2[0][1], pt2[0][2]]))>3:
                goal = np.array([pt2[0][0], pt2[0][1], pt2[0][2]])
                # print(closest_points, closest_distances)
                break

            else:
                continue
        world_data = {'bounds': bounds, 'blocks': blocks,'start': start,'goal': goal}
        return cls(world_data)
    @classmethod
    def fixed_block(cls, lower_bounds,upper_bounds,block_width, block_height, num_blocks,robot_radii,margin):
        bounds = {'extents': [lower_bounds[0], upper_bounds[0], lower_bounds[1], upper_bounds[1], lower_bounds[2], upper_bounds[2]]}
        blocks = []
        extents = list(np.array([-1.5, -1, -1, -0.5 , 0, 2]))
        blocks.append({'extents': extents, 'color': [1, 0, 0]})

        extents = list(np.array([0, 0.5, -1, -0.5 , 0, 2]))
        blocks.append({'extents': extents, 'color': [1, 0, 0]})

        extents = list(np.array([1.5, 2, 1, 1.5 , 0, 2]))
        blocks.append({'extents': extents, 'color': [1, 0, 0]})

        extents = list(np.array([1.5, 2, -1, -0.5 , 0, 2]))
        blocks.append({'extents': extents, 'color': [1, 0, 0]})

        start=np.array([-1.5,-1.5, 0.5])
        goal=np.array([2,0, 1.5])
        world_data = {'bounds': bounds, 'blocks': blocks,'start': start,'goal': goal}
        return cls(world_data)        



class ExpectTimeout(object):
    def __init__(self, seconds, print_traceback=True, mute=False):
        self.seconds_before_timeout = seconds
        self.original_trace_function = None
        self.end_time = None
        self.print_traceback = print_traceback
        self.mute = mute

    # Tracing function
    def check_time(self, frame, event, arg):
        if self.original_trace_function is not None:
            self.original_trace_function(frame, event, arg)

        current_time = time.time()
        if current_time >= self.end_time:
            raise TimeoutError

        return self.check_time

    # Begin of `with` block
    def __enter__(self):
        start_time = time.time()
        self.end_time = start_time + self.seconds_before_timeout

        self.original_trace_function = sys.gettrace()
        sys.settrace(self.check_time)
        return self

    # End of `with` block
    def __exit__(self, exc_type, exc_value, tb):
        self.cancel()

        if exc_type is None:
            return

        # An exception occurred
        if self.print_traceback:
            lines = ''.join(
                traceback.format_exception(
                    exc_type,
                    exc_value,
                    tb)).strip()
        else:
            lines = traceback.format_exception_only(
                exc_type, exc_value)[-1].strip()

#        if not self.mute:
#            print(lines, "(expected)", file=sys.stderr)
#        return True  # Ignore it

    def cancel(self):
        sys.settrace(self.original_trace_function)

    



if __name__ == '__main__':
    import argparse
    from pathlib import Path
    import matplotlib.pyplot as plt
    from flightsim.axes3ds import Axes3Ds

    parser = argparse.ArgumentParser(description='Display a map file in a Matplotlib window.')
    parser.add_argument('filename', help="Filename for map file json.")
    p = parser.parse_args()

    file = Path(p.filename)
    world = World.from_file(file)

    fig = plt.figure(f"{file.name}")
    ax = Axes3Ds(fig)
    world.draw(ax)

    plt.show()
