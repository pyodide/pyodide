*> \brief \b ZGEQRT
*
*  =========== DOCUMENTATION ===========
*
* Online html documentation available at
*            http://www.netlib.org/lapack/explore-html/
*
*> \htmlonly
*> Download ZGEQRT + dependencies
*> <a href="http://www.netlib.org/cgi-bin/netlibfiles.tgz?format=tgz&filename=/lapack/lapack_routine/zgeqrt.f">
*> [TGZ]</a>
*> <a href="http://www.netlib.org/cgi-bin/netlibfiles.zip?format=zip&filename=/lapack/lapack_routine/zgeqrt.f">
*> [ZIP]</a>
*> <a href="http://www.netlib.org/cgi-bin/netlibfiles.txt?format=txt&filename=/lapack/lapack_routine/zgeqrt.f">
*> [TXT]</a>
*> \endhtmlonly
*
*  Definition:
*  ===========
*
*       SUBROUTINE ZGEQRT( M, N, NB, A, LDA, T, LDT, WORK, INFO )
*
*       .. Scalar Arguments ..
*       INTEGER INFO, LDA, LDT, M, N, NB
*       ..
*       .. Array Arguments ..
*       COMPLEX*16 A( LDA, * ), T( LDT, * ), WORK( * )
*       ..
*
*
*> \par Purpose:
*  =============
*>
*> \verbatim
*>
*> ZGEQRT computes a blocked QR factorization of a complex M-by-N matrix A
*> using the compact WY representation of Q.
*> \endverbatim
*
*  Arguments:
*  ==========
*
*> \param[in] M
*> \verbatim
*>          M is INTEGER
*>          The number of rows of the matrix A.  M >= 0.
*> \endverbatim
*>
*> \param[in] N
*> \verbatim
*>          N is INTEGER
*>          The number of columns of the matrix A.  N >= 0.
*> \endverbatim
*>
*> \param[in] NB
*> \verbatim
*>          NB is INTEGER
*>          The block size to be used in the blocked QR.  MIN(M,N) >= NB >= 1.
*> \endverbatim
*>
*> \param[in,out] A
*> \verbatim
*>          A is COMPLEX*16 array, dimension (LDA,N)
*>          On entry, the M-by-N matrix A.
*>          On exit, the elements on and above the diagonal of the array
*>          contain the min(M,N)-by-N upper trapezoidal matrix R (R is
*>          upper triangular if M >= N); the elements below the diagonal
*>          are the columns of V.
*> \endverbatim
*>
*> \param[in] LDA
*> \verbatim
*>          LDA is INTEGER
*>          The leading dimension of the array A.  LDA >= max(1,M).
*> \endverbatim
*>
*> \param[out] T
*> \verbatim
*>          T is COMPLEX*16 array, dimension (LDT,MIN(M,N))
*>          The upper triangular block reflectors stored in compact form
*>          as a sequence of upper triangular blocks.  See below
*>          for further details.
*> \endverbatim
*>
*> \param[in] LDT
*> \verbatim
*>          LDT is INTEGER
*>          The leading dimension of the array T.  LDT >= NB.
*> \endverbatim
*>
*> \param[out] WORK
*> \verbatim
*>          WORK is COMPLEX*16 array, dimension (NB*N)
*> \endverbatim
*>
*> \param[out] INFO
*> \verbatim
*>          INFO is INTEGER
*>          = 0:  successful exit
*>          < 0:  if INFO = -i, the i-th argument had an illegal value
*> \endverbatim
*
*  Authors:
*  ========
*
*> \author Univ. of Tennessee
*> \author Univ. of California Berkeley
*> \author Univ. of Colorado Denver
*> \author NAG Ltd.
*
*> \ingroup complex16GEcomputational
*
*> \par Further Details:
*  =====================
*>
*> \verbatim
*>
*>  The matrix V stores the elementary reflectors H(i) in the i-th column
*>  below the diagonal. For example, if M=5 and N=3, the matrix V is
*>
*>               V = (  1       )
*>                   ( v1  1    )
*>                   ( v1 v2  1 )
*>                   ( v1 v2 v3 )
*>                   ( v1 v2 v3 )
*>
*>  where the vi's represent the vectors which define H(i), which are returned
*>  in the matrix A.  The 1's along the diagonal of V are not stored in A.
*>
*>  Let K=MIN(M,N).  The number of blocks is B = ceiling(K/NB), where each
*>  block is of order NB except for the last block, which is of order
*>  IB = K - (B-1)*NB.  For each of the B blocks, a upper triangular block
*>  reflector factor is computed: T1, T2, ..., TB.  The NB-by-NB (and IB-by-IB
*>  for the last block) T's are stored in the NB-by-K matrix T as
*>
*>               T = (T1 T2 ... TB).
*> \endverbatim
*>
*  =====================================================================
      SUBROUTINE ZGEQRT( M, N, NB, A, LDA, T, LDT, WORK, INFO )
*
*  -- LAPACK computational routine --
*  -- LAPACK is a software package provided by Univ. of Tennessee,    --
*  -- Univ. of California Berkeley, Univ. of Colorado Denver and NAG Ltd..--
*
*     .. Scalar Arguments ..
      INTEGER INFO, LDA, LDT, M, N, NB
*     ..
*     .. Array Arguments ..
      COMPLEX*16 A( LDA, * ), T( LDT, * ), WORK( * )
*     ..
*
* =====================================================================
*
*     ..
*     .. Local Scalars ..
      INTEGER    I, IB, IINFO, K
      LOGICAL    USE_RECURSIVE_QR
      PARAMETER( USE_RECURSIVE_QR=.TRUE. )
*     ..
*     .. External Subroutines ..
      EXTERNAL   ZGEQRT2, ZGEQRT3, ZLARFB, XERBLA
*     ..
*     .. Executable Statements ..
*
*     Test the input arguments
*
      INFO = 0
      IF( M.LT.0 ) THEN
         INFO = -1
      ELSE IF( N.LT.0 ) THEN
         INFO = -2
      ELSE IF( NB.LT.1 .OR. ( NB.GT.MIN(M,N) .AND. MIN(M,N).GT.0 ) )THEN
         INFO = -3
      ELSE IF( LDA.LT.MAX( 1, M ) ) THEN
         INFO = -5
      ELSE IF( LDT.LT.NB ) THEN
         INFO = -7
      END IF
      IF( INFO.NE.0 ) THEN
         CALL XERBLA( 'ZGEQRT', -INFO )
         RETURN
      END IF
*
*     Quick return if possible
*
      K = MIN( M, N )
      IF( K.EQ.0 ) RETURN
*
*     Blocked loop of length K
*
      DO I = 1, K,  NB
         IB = MIN( K-I+1, NB )
*
*     Compute the QR factorization of the current block A(I:M,I:I+IB-1)
*
         IF( USE_RECURSIVE_QR ) THEN
            CALL ZGEQRT3( M-I+1, IB, A(I,I), LDA, T(1,I), LDT, IINFO )
         ELSE
            CALL ZGEQRT2( M-I+1, IB, A(I,I), LDA, T(1,I), LDT, IINFO )
         END IF
         IF( I+IB.LE.N ) THEN
*
*     Update by applying H**H to A(I:M,I+IB:N) from the left
*
            CALL ZLARFB( 'L', 'C', 'F', 'C', M-I+1, N-I-IB+1, IB,
     $                   A( I, I ), LDA, T( 1, I ), LDT,
     $                   A( I, I+IB ), LDA, WORK , N-I-IB+1 )
         END IF
      END DO
      RETURN
*
*     End of ZGEQRT
*
      END
