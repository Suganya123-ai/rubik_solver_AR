// Converts the XREAL Eye's YUV_420_888 planes (Y full size, U and V half
// size, one channel each) to RGB with the full-range BT.601 matrix that
// Android cameras use. If colours look wrong, check which channel the SDK
// stores U/V in (r vs a) and whether the range is limited (16-235).
Shader "Hidden/RubikSolverAR/YuvToRgb"
{
    Properties
    {
        _MainTex ("Y", 2D) = "black" {}
        _UTex ("U", 2D) = "gray" {}
        _VTex ("V", 2D) = "gray" {}
    }
    SubShader
    {
        Cull Off ZWrite Off ZTest Always
        Pass
        {
            CGPROGRAM
            #pragma vertex vert_img
            #pragma fragment frag
            #include "UnityCG.cginc"

            sampler2D _MainTex;
            sampler2D _UTex;
            sampler2D _VTex;

            fixed4 frag (v2f_img i) : SV_Target
            {
                float y = tex2D(_MainTex, i.uv).r;
                float u = tex2D(_UTex, i.uv).r - 0.5;
                float v = tex2D(_VTex, i.uv).r - 0.5;
                float3 rgb = float3(y + 1.402 * v,
                                    y - 0.344136 * u - 0.714136 * v,
                                    y + 1.772 * u);
                return fixed4(saturate(rgb), 1);
            }
            ENDCG
        }
    }
}
