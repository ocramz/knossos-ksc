; RUN: ksc-mlir MLIR %s 2>&1 | FileCheck %s --check-prefix=MLIR
; RUN: ksc-mlir LLVM %s 2>&1 | FileCheck %s --check-prefix=LLVM

; Forward declaration, for use below
(edef fun Integer (Integer))
; MLIR: func @fun$ai(i64) -> i64
; LLVM: declare i64 @"fun$ai"(i64 %0)

; Just defines the variable, returns void
(def fun1 Integer () (
; MLIR: func @fun1() -> i64 {
; LLVM: define i64 @fun1() {
  (let (variable 123.456) 10)
; MLIR: %cst = constant 1.234560e+02 : f64
; MLIR: %c10{{.*}} = constant 10 : i64 
; MLIR: return %c10{{.*}} : i64

; LLVM: ret i64 10
))

; Return the value of x
(def fun2 Integer () (
; MLIR: func @fun2() -> i64 {
; LLVM: define i64 @fun2() {
  (let (x 10) x)
; MLIR: %c10{{.*}} = constant 10 : i64
; MLIR: return %c10{{.*}}

; LLVM: ret i64 10
))

; Call an operation with y, return the value
(def fun3 Integer (a : Integer) (
; MLIR: func @fun3$ai(%arg0: i64) -> i64 {
; LLVM: define i64 @"fun3$ai"(i64 %0) {
  (let (y 20) (add y a))
; MLIR: %c20{{.*}} = constant 20 : i64
; MLIR: %[[ret:[0-9]+]] = addi %c20{{.*}}, %arg0 : i64
; MLIR: return %[[ret]] : i64

; LLVM: %[[ret:[0-9]+]] = add i64 20, %0
; LLVM: ret i64 %[[ret]]
))

; Return the value of z, expanded from a function call
(def fun4 Integer () (
; MLIR: func @fun4() -> i64 {
; LLVM: define i64 @fun4() {
  (let (z (fun3 10)) z)
; MLIR generation creates SSA value if not constant
; MLIR: %c10{{.*}} = constant 10 : i64
; MLIR: %[[ret:[0-9]+]] = call @fun3$ai(%c10{{.*}}) : (i64) -> i64
; MLIR: return %[[ret]] : i64

; LLVM: %[[ret:[0-9]+]] = call i64 @"fun3$ai"(i64 10)
; LLVM: ret i64 %[[ret]]
))

; Nested lets
(def fun5 Integer (b : Integer) (
; MLIR: func @fun5$ai(%arg0: i64) -> i64 {
; LLVM: define i64 @"fun5$ai"(i64 %0) {
  (let (l1 (mul b b))
    (let (l2 (add b l1))
      (mul l1 l2)))
; MLIR: %[[mul:[0-9]+]] = muli %arg0, %arg0 : i64
; MLIR: %[[add:[0-9]+]] = addi %arg0, %[[mul]] : i64
; MLIR: %[[ret:[0-9]+]] = muli %[[mul]], %[[add]] : i64
; MLIR: return %[[ret]] : i64

; LLVM: %[[mul:[0-9]+]] = mul i64 %0, %0
; LLVM: %[[add:[0-9]+]] = add i64 %0, %[[mul]]
; LLVM: %[[ret:[0-9]+]] = mul i64 %[[mul]], %[[add]]
; LLVM: ret i64 %[[ret]]
))
