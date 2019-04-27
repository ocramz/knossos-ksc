﻿/// These are stubs that we expect Knossos to substitute later, they may want to be given implementations
/// so that debugging on the F# side is possible.
module Knossos

open DV
type Vec = Vector<float>
type Mat = Vector<Vector<float>>

let invSqrtGaussian_sample _ _ _ = 0.0
type RNG =
    class end
let Q = id
let categorical_sample _ _ : int = 0


let inline size (v: Vector<'T>) = v.Length

let inline build n (f : int -> 'T) = Vector.init n f
let inline build2 m n (f : int -> int -> float) = Vector.init m (fun i -> Vector.init n (f i))
let inline sum v = Vector.sum v
let inline mul (a: Vector<Vector<float>>) (b: Vector<float>) : Vector<float> = 
    sum(build (size a) (fun i -> a.[i] * b.[i]))

let inline max (a: Vector<float>) = a.GetMaxBy( fun x->x )
let inline expv (a: Vector<float>) = Vector.map exp a
//let inline sqnorm (a: Vector<'a>) = a.GetL2NormSq()
let inline sqnorm (a: Vector<float>) = a.GetL2NormSq()
let gammaLn (a: float) = a

